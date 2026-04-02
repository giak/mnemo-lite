# EPIC-24: Auto-Save Daemon - SIMULATION & DEEP ANALYSIS

**Date**: 2025-10-29
**Version**: 1.0.0 - ULTRATHINK SIMULATION
**Status**: 🔬 CRITICAL ANALYSIS

---

## 🎯 Méthodologie

**Approche**: Simulation mentale complète de l'implémentation pour identifier TOUS les problèmes AVANT de coder.

**Simulations**:
1. Startup scenario (cold start)
2. Runtime scenario (polling active)
3. Crash scenarios (daemon, API, DB)
4. Performance scenarios (load testing)
5. Edge cases (race conditions, corrupted data)
6. User portability (different environments)

---

## 🚀 SIMULATION 1: Cold Start (First Time)

### Timeline

```
T=0s     User: docker compose up
T=0.5s   Docker: Pull images if needed
T=2s     Docker: Start db container
T=3s     Docker: Start api container
T=3.5s   Container: Execute command
         sh -c "python3 /app/scripts/conversation-daemon.py & uvicorn ..."
T=4s     Daemon: Process spawned in background
T=4.1s   API: Uvicorn starts, loads FastAPI app
T=4.5s   Daemon: Initialize
         ├─> Load state from /tmp/conversation-daemon-state.json
         │   → File doesn't exist (first run)
         │   → Create empty state
         ├─> Connect to PostgreSQL
         │   → DB might not be ready yet! ⚠️
         │   → PROBLEM #1: Race condition with DB startup
         └─> Initialize MnemoLite services
T=5s     Daemon: Start polling
         ├─> Scan /home/user/.claude/projects/
         │   → Find 45 transcript files (historical)
         │   → Total size: ~200MB of JSONL
         ├─> FOR EACH of 45 files:
         │   ├─> Open file
         │   ├─> Read ALL lines (no last_position yet)
         │   ├─> Parse JSONL
         │   ├─> Extract user+assistant pairs
         │   └─> Save each to DB
         │       └─> Generate embedding (768D)
         └─> Estimated time: 45 files × 2-5 exchanges avg × 50ms = 5-10 seconds

T=15s    Daemon: First iteration complete
         ├─> Saved 152 conversations
         ├─> State file created with hashes
         └─> Enter sleep(30)

T=20s    User: Checks logs
         docker compose logs api
         → Sees both API logs and DAEMON logs mixed
         → PROBLEM #2: Logs difficiles à lire

T=45s    Daemon: Iteration 2
         ├─> Scan files again
         ├─> Load state (last_position per file)
         ├─> Parse only NEW lines (incremental)
         └─> Find 0 new exchanges (nothing happened)
         └─> Sleep(30)
```

### Problems Identified

**PROBLEM #1: DB Race Condition**
```python
# Daemon starts at T=4s
# DB might not be ready until T=5s
# → Connection error

SOLUTION:
- Add retry loop on DB connection
- Wait up to 30s for DB to be ready
- Log warnings but don't crash
```

**PROBLEM #2: Mixed Logs**
```
[API] INFO: Started server process
[DAEMON] Daemon started
[API] INFO: Waiting for application startup
[DAEMON] Found 45 transcripts
[API] INFO: Application startup complete
[DAEMON] ✓ Saved 152 conversations
```

**Impact**: Hard to follow, but acceptable with grep
**Mitigation**: Prefix all daemon logs with `[DAEMON]`
**Alternative**: Write to separate file `/tmp/daemon.log`

**PROBLEM #3: Initial Import Blocking**
- First iteration takes 5-10s
- During this time, daemon is busy
- API is NOT blocked (separate process) ✅
- But if user queries DB immediately, might see partial data

**SOLUTION**: Non-blocking, acceptable

---

## 🔄 SIMULATION 2: Runtime (Steady State)

### Scenario: Active Claude Code Session

```
T=0      User starts Claude Code session
         claude
         → Creates new transcript: 6f3a2b1c-9d4e-4a5f-8b2c-1d7e9f0a3c5b.jsonl

T=30s    User has 2 exchanges with Claude
         Transcript now has:
         - 2 user messages
         - 2 assistant messages

T=45s    Daemon: Iteration N
         ├─> Scan files
         │   → New file detected: 6f3a2b1c-9d4e-4a5f-8b2c-1d7e9f0a3c5b.jsonl
         │   → No last_position (new file)
         ├─> Parse entire file
         │   → Extract 2 exchanges
         ├─> Compute hashes
         │   → hash1 = "a3f4d89e2c1b5f6a"
         │   → hash2 = "b2e8c71f9d3a4e5c"
         ├─> Check if in saved_hashes
         │   → Not found (new)
         ├─> Save to DB
         │   ├─> Exchange 1 → DB (50ms)
         │   └─> Exchange 2 → DB (50ms)
         └─> Update state
             ├─> last_position = 12,345
             ├─> Add hashes to saved_hashes
             └─> Save state file

T=46s    Daemon: Sleep(30)

T=60s    User has 1 more exchange

T=76s    Daemon: Iteration N+1
         ├─> Scan files
         │   → File 6f3a2b1c... modified (mtime changed)
         ├─> Seek to last_position (12,345)
         ├─> Read new lines only
         │   → 1 user message
         │   → 1 assistant message
         ├─> Extract 1 exchange
         ├─> Save to DB (50ms)
         └─> Update state
```

### Performance Analysis

**Per Iteration Cost**:
- Scan directory: ~1ms
- Read state file: ~1ms
- For each active file (assume 3 active sessions):
  - Seek to position: ~0.1ms
  - Read new lines: ~0.5ms (usually small)
  - Parse JSONL: ~1ms
  - Extract exchanges: ~0.5ms
- Save new exchanges: 50ms × count
- Write state file: ~2ms

**Total**: ~10ms + (50ms × new_exchanges)

**Typical case**: 0-2 new exchanges per iteration
**Time**: ~10-110ms per iteration
**CPU**: ~0.3% average (110ms / 30s)

**Verdict**: ✅ Performance acceptable

---

## 💥 SIMULATION 3: Crash Scenarios

### Scenario 3A: Daemon Crashes

```
T=0      Daemon running normally
T=45s    Daemon: Iteration N
         ├─> Parse transcript
         ├─> EXCEPTION: MemoryError (unlikely but possible)
         └─> Process dies

T=46s    Container status?
         ├─> API process still running (separate process)
         ├─> Container stays UP (API is foreground)
         └─> PROBLEM: Daemon dead, no restart

User view:
- API still works ✅
- But conversations NOT being saved ❌
- No visible error (unless checking logs)
```

**PROBLEM #4: Daemon Crash Undetected**

**Current approach**: No supervision
**Impact**: Silent failure, user doesn't know

**SOLUTIONS**:

**Option A: Restart on Crash (bash loop)**
```bash
# docker-compose.yml
command: >
  sh -c "
    while true; do
      python3 /app/scripts/conversation-daemon.py
      echo '[ERROR] Daemon crashed, restarting in 5s...'
      sleep 5
    done &
    uvicorn api.main:app --host 0.0.0.0 --port 8000
  "
```
✅ Simple
✅ Auto-restart
⚠️ Might hide bugs (infinite restart loop)

**Option B: Supervisord**
❌ External dependency (violates constraint)

**Option C: Docker Healthcheck**
```yaml
healthcheck:
  test: ["CMD", "pgrep", "-f", "conversation-daemon.py"]
  interval: 30s
```
⚠️ Detects crash but doesn't restart

**Option D: Robust Error Handling (no crash)**
```python
async def poll_loop():
    while True:
        try:
            await poll_iteration()
        except Exception as e:
            logger.error(f"Error in iteration: {e}")
            # Log but DON'T crash
        await asyncio.sleep(30)
```
✅ Simplest
✅ No external deps
✅ Daemon never crashes (just logs errors)

**RECOMMENDATION**: Option D + Option A (belt and suspenders)

---

### Scenario 3B: Database Crashes

```
T=0      System running normally
T=45s    DB container crashes (killed by OOM, etc.)
T=46s    Daemon: Iteration N
         ├─> Try to save conversation
         ├─> await memory_repo.create_memory(...)
         └─> EXCEPTION: asyncpg.exceptions.ConnectionDoesNotExistError

T=47s    Daemon: Error handling
         ├─> Log error
         ├─> Sleep(30) and retry next iteration

T=77s    Daemon: Iteration N+1
         ├─> Try to reconnect to DB
         ├─> If DB still down: log error, continue
         └─> If DB back up: retry saving queued conversations
```

**PROBLEM #5: Lost Conversations During DB Downtime**

**Current approach**: Skip and hope next iteration succeeds
**Impact**: Conversations from DB downtime window are lost

**SOLUTION**: Implement queue
```python
failed_queue = []

async def save_with_retry(exchange):
    try:
        await save_to_db(exchange)
    except DBError:
        failed_queue.append(exchange)
        logger.error("Queued for retry")

async def poll_iteration():
    # First, retry failed ones
    for exchange in failed_queue.copy():
        try:
            await save_to_db(exchange)
            failed_queue.remove(exchange)
        except:
            pass  # Keep in queue

    # Then process new ones
    await process_new_exchanges()
```

✅ No conversations lost
⚠️ Queue can grow if DB down for long time
**Mitigation**: Limit queue size to 1000, then drop oldest

---

### Scenario 3C: API Crashes

```
T=0      Both API and Daemon running
T=45s    API: Uncaught exception in route handler
         └─> Uvicorn process exits (code 1)

T=46s    Container status?
         ├─> Daemon process still running (background)
         ├─> But Uvicorn (foreground) exited
         └─> Docker sees container as FAILED
         └─> Container exits (both processes killed)

T=47s    Docker restart policy (if enabled)
         └─> Container restarts
         └─> Both API and Daemon start fresh
```

**Impact**:
- Container restart OK ✅
- Daemon loses in-memory state ❌
- But state file persisted, so can resume ✅

**Verdict**: Acceptable behavior

---

## ⚡ SIMULATION 4: Performance & Load

### Scenario 4A: Many Active Sessions

```
Assumptions:
- User has 10 simultaneous Claude Code sessions
- Each session generates 1 exchange per minute
- Daemon polls every 30s

T=0      Daemon scans 10 active transcripts
         ├─> Each file: seek + read (~1ms)
         └─> Total scan time: 10ms

T=30s    5 new exchanges across various sessions
         ├─> Parse: 5 × 1ms = 5ms
         ├─> Save: 5 × 50ms = 250ms
         └─> Total: ~260ms

T=60s    5 more exchanges
         └─> Same: ~260ms

CPU usage: 260ms / 30s = 0.87%
```

**Verdict**: ✅ Scales well even with many sessions

---

### Scenario 4B: Large Transcript File

```
Scenario:
- One transcript has 10,000 exchanges (197MB JSONL)
- Daemon does incremental parsing (seek to last_position)

T=0      Initial import (first time)
         ├─> Parse entire 197MB file
         ├─> Extract 10,000 exchanges
         ├─> Time: 10,000 × 50ms = 500 seconds = 8.3 minutes
         └─> PROBLEM #6: Initial import too slow!

T=500s   Import complete
         └─> State saved (last_position = 197MB)

T=530s   New exchange added to file
         ├─> File now 197.1MB
         ├─> Seek to 197MB (instant)
         ├─> Read last 0.1MB (fast)
         └─> Parse 1 exchange (50ms)
         └─> ✅ Fast after initial import
```

**PROBLEM #6: Initial Import Bottleneck**

**Impact**:
- First `docker compose up` might take 5-10 minutes if many historical conversations
- User might think it's stuck

**SOLUTIONS**:

**Option A: Async Initial Import**
```python
async def daemon_start():
    # Start polling immediately with empty state
    asyncio.create_task(poll_loop())

    # Do initial import in background
    await initial_import_all_transcripts()
```
✅ User doesn't wait
⚠️ Complex (two concurrent operations)

**Option B: Limit Initial Import**
```python
# Only import conversations from last 7 days
if transcript.stat().st_mtime < (now - 7*86400):
    skip
```
✅ Fast startup
⚠️ User loses old conversations (can run manual import later)

**Option C: Progress Logging**
```python
for i, transcript in enumerate(transcripts):
    logger.info(f"Processing {i+1}/{len(transcripts)}: {transcript.name}")
    await process_transcript(transcript)
```
✅ User sees progress
⚠️ Still takes time

**Option D: Make Initial Import Optional**
```python
# Only import if env var set
if os.getenv("IMPORT_HISTORICAL", "false") == "true":
    await initial_import()
else:
    logger.info("Skipping historical import (enable with IMPORT_HISTORICAL=true)")
```
✅ Fast startup by default
✅ User can opt-in for full import
⚠️ Requires user to know about this

**RECOMMENDATION**: Option D + Option C (opt-in with progress)

---

## 🐛 SIMULATION 5: Edge Cases & Race Conditions

### Edge Case 5A: Incomplete JSONL Line

```
Scenario: Claude is writing a message while daemon reads

Transcript file:
{"role": "user", "content": "Hello"}
{"role": "assistant", "content": "Hi there! How can I h

[DAEMON reads file HERE]

T+0.1s: Claude finishes writing
{"role": "user", "content": "Hello"}
{"role": "assistant", "content": "Hi there! How can I help?"}
```

**Problem**: Daemon reads incomplete line
**Error**: `json.JSONDecodeError: Unterminated string`

**SOLUTION**:
```python
for line in file:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        # Incomplete line, skip
        # Will be read on next iteration (complete)
        continue
```

**Impact**:
- Exchange delayed by 30s (one iteration)
- But not lost ✅
- No crash ✅

**Verdict**: Acceptable behavior

---

### Edge Case 5B: File Renamed/Deleted During Iteration

```
T=0      Daemon: Start iteration
         ├─> Scan directory
         └─> File list: [session1.jsonl, session2.jsonl]

T=1s     User: Deletes old session
         rm ~/.claude/projects/session1.jsonl

T=2s     Daemon: Try to open session1.jsonl
         └─> FileNotFoundError

SOLUTION:
try:
    with open(transcript_path) as f:
        parse(f)
except FileNotFoundError:
    logger.warning(f"File disappeared: {transcript_path}")
    continue  # Skip, not an error
```

**Verdict**: Handled gracefully ✅

---

### Edge Case 5C: Corrupted State File

```
Scenario: Daemon killed mid-write to state file

/tmp/conversation-daemon-state.json:
{
  "version": "1.0.0",
  "transcripts": {
    "session1.jsonl": {
      "last_position": 123

[FILE TRUNCATED - DAEMON KILLED]

SOLUTION:
def load_state():
    try:
        with open(state_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning("State file corrupted or missing, starting fresh")
        return empty_state()
```

**Impact**:
- Daemon starts fresh (no last_position)
- Will re-parse transcripts ⚠️
- But dedup by hash prevents duplicates ✅

**Verdict**: Recoverable, acceptable

---

## 🌍 SIMULATION 6: User Portability

### Scenario 6A: Different Claude Projects Directory

```
User A (default):
~/.claude/projects/-home-giak-Work-MnemoLite/

User B (custom workspace):
~/.claude/projects/-home-user-projects-myproject/

User C (different home):
~/.claude/projects/-mnt-data-projects-project1/
```

**PROBLEM #7: Hardcoded Path**

**Current approach**: Hardcoded in docker-compose.yml
```yaml
volumes:
  - ~/.claude/projects/-home-giak-Work-MnemoLite:/home/user/.claude/projects:ro
```

**SOLUTION**: Use environment variable
```yaml
# docker-compose.yml
volumes:
  - ${CLAUDE_PROJECTS_DIR:-~/.claude/projects/-home-giak-Work-MnemoLite}:/home/user/.claude/projects:ro
```

**Usage**:
```bash
# Default
docker compose up

# Custom
CLAUDE_PROJECTS_DIR=~/.claude/projects/-home-user-projects-myproject docker compose up
```

**Documentation needed**:
- README must explain this
- Provide script to detect correct path automatically

```bash
# scripts/detect-claude-projects.sh
#!/bin/bash
# Detect Claude Code projects directory for current workspace

WORKSPACE=$(pwd)
PROJECT_HASH=$(echo -n "$WORKSPACE" | sha256sum | cut -d' ' -f1)
PROJECT_DIR="$HOME/.claude/projects/-$(echo $WORKSPACE | sed 's/\//-/g')"

if [ -d "$PROJECT_DIR" ]; then
    echo "Found: $PROJECT_DIR"
    echo "export CLAUDE_PROJECTS_DIR=$PROJECT_DIR"
else
    echo "Not found. Using default."
fi
```

**Verdict**: Solvable with env var + documentation

---

### Scenario 6B: Windows User (WSL)

```
Windows path:
C:\Users\user\projects\MnemoLite

WSL path:
/mnt/c/Users/user/projects/MnemoLite

Claude projects path:
/home/user/.claude/projects/-mnt-c-Users-user-projects-MnemoLite
```

**PROBLEM #8: Path Conversion**

**SOLUTION**: Document WSL path conversion
```bash
# On WSL
cd /mnt/c/Users/user/projects/MnemoLite
export CLAUDE_PROJECTS_DIR=~/.claude/projects/$(pwd | sed 's/\//-/g')
docker compose up
```

**Verdict**: Doable but needs clear documentation

---

## 🔐 SIMULATION 7: Security Considerations

### Security Issue 7A: Read-Only Mount

```yaml
volumes:
  - ~/.claude/projects:/home/user/.claude/projects:ro  # READ-ONLY
```

**Why :ro?**
- Daemon should NEVER modify transcripts
- Only read for parsing
- Safety: Prevents accidental corruption

**Verdict**: ✅ Good practice

---

### Security Issue 7B: Credentials in Transcripts

```
Scenario: User accidentally pastes API key in Claude conversation

Transcript contains:
{"role": "user", "content": "My API key is sk-1234567890abcdef"}

Daemon saves to DB:
- Content includes API key
- Stored in PostgreSQL
- Embeddings might encode key
```

**PROBLEM #9: Sensitive Data Leakage**

**SOLUTION**: Add optional sanitization
```python
SENSITIVE_PATTERNS = [
    r'sk-[a-zA-Z0-9]{40}',  # OpenAI keys
    r'ghp_[a-zA-Z0-9]{36}',  # GitHub tokens
    # etc.
]

def sanitize_content(text):
    for pattern in SENSITIVE_PATTERNS:
        text = re.sub(pattern, '[REDACTED]', text)
    return text
```

**Configuration**:
```yaml
# docker-compose.yml
environment:
  - SANITIZE_CONVERSATIONS=true  # Default: false
```

**Verdict**: Optional feature, document risk

---

## 📊 SUMMARY: Problems Found

| # | Problem | Severity | Solution | Status |
|---|---------|----------|----------|--------|
| 1 | DB race condition on startup | Medium | Retry loop (30s) | ✅ Solvable |
| 2 | Mixed logs (API + Daemon) | Low | Prefix `[DAEMON]` | ✅ Acceptable |
| 3 | Initial import blocking | Low | Non-blocking | ✅ By design |
| 4 | Daemon crash undetected | High | Robust error handling + restart loop | ✅ Solvable |
| 5 | Lost conversations during DB downtime | Medium | Retry queue (max 1000) | ✅ Solvable |
| 6 | Initial import slow (large history) | Medium | Opt-in historical import | ✅ Solvable |
| 7 | Hardcoded projects path | High | Environment variable | ✅ Solvable |
| 8 | WSL path conversion | Low | Documentation | ✅ Solvable |
| 9 | Sensitive data leakage | Medium | Optional sanitization | ⚠️ Document risk |

---

## 🎯 REVISED ARCHITECTURE

### Key Changes After Simulation

1. **Restart Loop** (Problem #4)
```bash
command: >
  sh -c "
    (while true; do
      python3 /app/scripts/conversation-daemon.py || sleep 5
    done) &
    uvicorn api.main:app --host 0.0.0.0 --port 8000
  "
```

2. **Robust Error Handling** (Problem #4, #5)
```python
async def poll_loop():
    retry_queue = []

    while True:
        try:
            await process_retry_queue(retry_queue)
            await poll_iteration(retry_queue)
        except Exception as e:
            logger.error(f"Iteration error: {e}", exc_info=True)

        await asyncio.sleep(30)
```

3. **DB Connection Retry** (Problem #1)
```python
async def wait_for_db(max_wait=30):
    for i in range(max_wait):
        try:
            await db.connect()
            logger.info("DB connection established")
            return
        except:
            logger.info(f"Waiting for DB... ({i+1}/{max_wait})")
            await asyncio.sleep(1)

    raise Exception("DB not available after 30s")
```

4. **Environment Variable** (Problem #7)
```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ${CLAUDE_PROJECTS_DIR:-~/.claude/projects}:/home/user/.claude/projects:ro
    environment:
      - IMPORT_HISTORICAL=${IMPORT_HISTORICAL:-false}
      - SANITIZE_CONVERSATIONS=${SANITIZE_CONVERSATIONS:-false}
```

5. **Helper Script** (Problem #7)
```bash
# scripts/setup-env.sh
#!/bin/bash
# Auto-detect Claude projects directory

WORKSPACE=$(pwd)
PROJECT_DIR=$(find ~/.claude/projects -maxdepth 1 -type d -name "*$(basename $WORKSPACE)*" | head -1)

if [ -z "$PROJECT_DIR" ]; then
    echo "Could not detect Claude projects directory"
    echo "Please set manually: export CLAUDE_PROJECTS_DIR=..."
    exit 1
fi

echo "Detected: $PROJECT_DIR"
echo "export CLAUDE_PROJECTS_DIR=$PROJECT_DIR" > .env.local
echo "✓ Created .env.local"
```

---

## ✅ FINAL VERDICT

### Is This Solution Viable?

**YES**, with modifications identified in simulation.

### Confidence Level

**85%** - High confidence with following caveats:

**Must Have**:
- ✅ Restart loop (Problem #4)
- ✅ DB retry logic (Problem #1)
- ✅ Environment variable for path (Problem #7)
- ✅ Robust error handling (Problem #4, #5)

**Should Have**:
- ✅ Retry queue for failed saves (Problem #5)
- ✅ Opt-in historical import (Problem #6)
- ✅ Setup helper script (Problem #7)

**Nice to Have**:
- ⚠️ Sanitization (Problem #9) - Document instead
- ⚠️ Separate log file - Keep mixed logs with prefix

### Remaining Risks

1. **Path Detection** - 15% risk
   - Different environments might have unexpected paths
   - Mitigation: Good documentation + helper script

2. **Initial Import Time** - 10% risk
   - Large history might still take time even with opt-in
   - Mitigation: Progress logging + async

3. **Windows/WSL** - 10% risk
   - Path conversion might have edge cases
   - Mitigation: Test on WSL, document

4. **Sensitive Data** - 5% risk
   - Users might save sensitive data unknowingly
   - Mitigation: Document + optional sanitization

---

## 🚀 GO / NO-GO Decision

### Recommendation: **GO** ✅

**Justification**:
- All critical problems have solutions
- Architecture is sound after revisions
- Risks are manageable with documentation
- User experience is acceptable
- Performance is good
- Maintenance is reasonable

### Next Steps

1. **Implementation** (~3h with all fixes)
   - Create daemon script with all error handling
   - Modify docker-compose.yml with restart loop
   - Create setup helper script
   - Add environment variables

2. **Testing** (~1h)
   - Test all 7 scenarios from simulations
   - Verify error recovery
   - Test on clean state

3. **Documentation** (~1h)
   - README with setup instructions
   - Environment variables
   - Troubleshooting guide
   - Known limitations

**Total ETA**: 5h (instead of 2h, due to robustness improvements)

---

**Ready to implement with confidence?**

**Version**: 1.0.0 - POST-SIMULATION
**Date**: 2025-10-29
**Author**: Claude Code Assistant (Ultrathink Mode)
**EPIC**: EPIC-24 (Auto-Save Conversations)
**Status**: ✅ VALIDATED - READY FOR IMPLEMENTATION
