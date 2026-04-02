# EPIC-24 Deprecated Files Archive

**Date**: 2025-10-29
**Reason**: Architectural pivot from MCP Hooks to Daemon Polling

## Context

These files represent the initial MCP hooks-based implementation of EPIC-24 auto-save conversations. This approach was deprecated due to Claude Code Bug #10401, which requires `--debug hooks` flag for hooks to execute.

## Deprecated Approach: MCP Hooks

**Files archived:**
- `AUTO-SAVE-SIMPLE.md` - Guide for UserPromptSubmit hook approach
- `hooks_stop/` - Stop hook implementation (non-functional)

**Why deprecated:**
- Claude Code Bug #10401: Hooks require `--debug` flag to execute
- Unreliable in production (hooks may not fire)
- User feedback: "ça ne fonctionne pas" (repeated failures)

## Current Approach: Daemon Polling

**Status**: ✅ OPERATIONAL (7,975 conversations imported)

**Implementation**:
- `scripts/conversation-auto-import.sh` - Daemon polling every 30s
- `api/routes/conversations_routes.py` - Parser with tool_result filtering
- `docker-compose.yml` - Daemon launch + 3-layer monitoring

**Documentation**: See `EPIC-24_README.md` (v2.0.0) for current implementation

**Completion Report**: See `EPIC-24_BUGFIX_CRITICAL_COMPLETION_REPORT.md` for pivot details

---

**Note**: These files are kept for historical reference and to understand the evolution of the auto-save system. Do NOT use this approach in production.
