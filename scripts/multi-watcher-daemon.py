#!/usr/bin/env python3
"""
MnemoLite Multi-Source Conversation Watcher Daemon

Monitors 4 AI coding tools and imports conversations into MnemoLite:
  - Claude Code  (~/.claude/projects/)
  - Codebuff     (~/.config/manicode/projects/)
  - OpenCode     (~/.local/share/opencode/opencode.db)
  - KiloCode     (~/.vscode[-server]/globalStorage/kilocode.kilo-code/tasks/)

Architecture: Polling-based (no watchdog dependency).
Each source polls at its own interval and posts to the MnemoLite API.

Usage:
    python3 scripts/multi-watcher-daemon.py                      # All sources
    python3 scripts/multi-watcher-daemon.py --source codebuff    # One source
    python3 scripts/multi-watcher-daemon.py --dry-run             # Preview only
    python3 scripts/multi-watcher-daemon.py --api-url http://localhost:8001

Author: Codebuff Assistant
EPIC: Multi-Source Conversation Import
"""

import asyncio
import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.core import get_settings

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Install: pip3 install aiohttp")
    sys.exit(1)

try:
    import structlog
except ImportError:
    structlog = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _add_watcher_name(_, __, event_dict):
    """Attach a fixed logger name to events.

    A PrintLogger has no `name` attribute, so structlog.stdlib.add_logger_name
    would raise AttributeError. The daemon always logs under "watcher".
    """
    event_dict["logger"] = "watcher"
    return event_dict


def _configure_logging():
    """Configure structlog for the daemon.

    Uses structlog when available (inside Docker container), falls back to
    a lightweight stub that mimics structlog's API via print() for local runs.

    Set WATCHER_LOG_FORMAT=json env var to emit JSON logs
    (useful when running in Docker alongside the API for OpenObserve ingestion).

    Note: uses structlog.wrap_logger() (local config) instead of
    structlog.configure() (global config). The global configure poisoned the
    structlog config for any process importing this module (e.g. pytest test
    collection), and crashed on add_logger_name over a PrintLogger.
    """
    log_json = get_settings().WATCHER_LOG_FORMAT == "json"

    if structlog is not None:
        renderer = (
            structlog.processors.JSONRenderer()
            if log_json
            else structlog.dev.ConsoleRenderer()
        )
        return structlog.wrap_logger(
            structlog.PrintLogger(),
            processors=[
                structlog.stdlib.add_log_level,
                _add_watcher_name,
                structlog.processors.TimeStamper(fmt="iso"),
                renderer,
            ],
        )
    else:
        # Fallback: simple logger that mimics structlog's keyword API
        class _PrintLogger:
            """Minimal structlog-compatible logger using print()."""
            def _log(self, level: str, event: str, **kwargs):
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                parts = [f"[{level}] {ts} {event}"]
                for k, v in kwargs.items():
                    parts.append(f"{k}={v}")
                print(" ".join(parts))

            def info(self, event: str, **kwargs): self._log("INFO", event, **kwargs)
            def warning(self, event: str, **kwargs): self._log("WARN", event, **kwargs)
            def error(self, event: str, **kwargs): self._log("ERROR", event, **kwargs)
            def debug(self, event: str, **kwargs): self._log("DEBUG", event, **kwargs)

        return _PrintLogger()


logger = _configure_logging()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ConversationPair:
    """A single user-assistant exchange ready for import."""
    user_message: str
    assistant_message: str
    project_name: str      # lowercase, e.g. "mnemolite"
    session_id: str
    timestamp: str         # ISO 8601 or empty
    source_tag: str        # "claude-code" | "codebuff" | "opencode" | "kilocode"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            (self.user_message + self.assistant_message).encode()
        ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

class WatcherState:
    """Persists import state to avoid re-processing on restart."""

    def __init__(self, path: str = None):
        self.path = Path(path or os.getenv(
            "MNEMO_WATCHER_STATE",
            str(Path.home() / ".local" / "share" / "mnemo" / "multi-watcher-state.json")
        ))
        self.state: Dict = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {"sources": {}, "saved_hashes": [], "stats": {}}

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.state["saved_hashes"] = list(self._hash_set)[-10000:]
            self.path.write_text(json.dumps(self.state, indent=2))
        except Exception as e:
            logger.warning("state_save_failed", error=str(e))

    @property
    def _hash_set(self) -> Set[str]:
        # Cache the set for O(1) lookups; rebuild only when stale
        if not hasattr(self, '_cached_hash_set'):
            self._cached_hash_set = set(self.state.get("saved_hashes", []))
        return self._cached_hash_set

    def is_saved(self, content_hash: str) -> bool:
        return content_hash in self._hash_set

    def mark_saved(self, content_hash: str):
        self.state.setdefault("saved_hashes", []).append(content_hash)
        if hasattr(self, '_cached_hash_set'):
            self._cached_hash_set.add(content_hash)

    def get_source_state(self, source_name: str) -> Dict:
        self.state.setdefault("sources", {}).setdefault(source_name, {})
        return self.state["sources"][source_name]

    def set_source_state(self, source_name: str, data: Dict):
        self.state.setdefault("sources", {})[source_name] = data


# ---------------------------------------------------------------------------
# Base source
# ---------------------------------------------------------------------------

class BaseSourceWatcher(ABC):
    """Abstract base for conversation source watchers."""

    POLL_INTERVAL: int = 30  # seconds

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 project_filter: Optional[str] = None):
        self.state = state
        self.api_url = api_url
        self.dry_run = dry_run
        self.project_filter = project_filter.lower() if project_filter else None
        self._session: Optional[aiohttp.ClientSession] = None
        self.name = self.__class__.__name__

    async def ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @abstractmethod
    async def poll(self) -> List[ConversationPair]:
        """Poll source and return NEW conversation pairs since last poll."""
        ...

    def _extract_project_name(self, raw_path: str) -> str:
        """Resolve project name to lowercase per MnemoLite rules."""
        return Path(raw_path).name.lower()

    def _decode_claude_dir(self, encoded_dir: str) -> str:
        """Decode Claude Code encoded directory name to real path."""
        match = re.match(r'^-home-([^-]+)-Work-(.+)$', encoded_dir)
        if match:
            return f"/home/{match.group(1)}/Work/{match.group(2)}"
        match = re.match(r'^-home-([^-]+)-projects-(.+)$', encoded_dir)
        if match:
            return f"/home/{match.group(1)}/projects/{match.group(2)}"
        return ""

    async def save_pair(self, pair: ConversationPair) -> bool:
        """Post conversation pair to MnemoLite API."""
        # Project filter: skip conversations from other projects
        if self.project_filter and pair.project_name != self.project_filter:
            logger.debug("project_filtered",
                         source=pair.source_tag,
                         project=pair.project_name,
                         filter=self.project_filter)
            return False

        if self.state.is_saved(pair.content_hash):
            return False

        if self.dry_run:
            logger.info("dry_run_save",
                         project=pair.project_name,
                         source=pair.source_tag,
                         hash=pair.content_hash,
                         user_preview=pair.user_message[:50])
            self.state.mark_saved(pair.content_hash)
            return True

        await self.ensure_session()
        try:
            async with self._session.post(
                f"{self.api_url}/v1/conversations/save",
                json={
                    "user_message": pair.user_message,
                    "user_message_clean": pair.user_message[:100],
                    "assistant_message": pair.assistant_message,
                    "project_name": pair.project_name,
                    "session_id": pair.session_id,
                    "timestamp": pair.timestamp,
                    "source": pair.source_tag,
                }
            ) as resp:
                if resp.status == 200:
                    self.state.mark_saved(pair.content_hash)
                    return True
                else:
                    body = await resp.text()
                    logger.error("api_error_status",
                                 status=resp.status,
                                 body_preview=body[:200])
                    return False
        except Exception as e:
            logger.error("api_call_failed", error=str(e))
            return False


# ---------------------------------------------------------------------------
# Claude Code source
# ---------------------------------------------------------------------------

class ClaudeCodeSource(BaseSourceWatcher):
    """Watches ~/.claude/projects/ for JSONL transcripts."""

    POLL_INTERVAL = 30

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 projects_dir: str = None, project_filter: Optional[str] = None):
        super().__init__(state, api_url, dry_run, project_filter)
        self.projects_dir = Path(
            projects_dir or get_settings().CLAUDE_PROJECTS_DIR or os.getenv("CLAUDE_PROJECTS_DIR",
                                      str(Path.home() / ".claude" / "projects"))
        )

    async def poll(self) -> List[ConversationPair]:
        if not self.projects_dir.exists():
            return []

        pairs = []
        src_state = self.state.get_source_state("claude-code")

        for transcript_file in self.projects_dir.glob("**/*.jsonl"):
            if transcript_file.name.startswith("agent-"):
                continue

            # Cooldown: skip files modified < 60s ago (still being written)
            file_age = time.time() - transcript_file.stat().st_mtime
            if file_age < 60:
                continue

            file_key = str(transcript_file)
            last_size = src_state.get(file_key, 0)
            current_size = transcript_file.stat().st_size

            if current_size <= last_size:
                continue  # No new content

            try:
                new_pairs = self._parse_transcript(transcript_file, src_state)
                pairs.extend(new_pairs)
                src_state[file_key] = current_size
            except Exception as e:
                logger.warning("parse_error", source="claude-code", file=transcript_file.name, error=str(e))

        self.state.set_source_state("claude-code", src_state)
        return pairs

    def _parse_transcript(self, path: Path, src_state: Dict) -> List[ConversationPair]:
        messages = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if 'message' in msg and 'role' in msg['message']:
                        messages.append(msg['message'])
                except json.JSONDecodeError:
                    continue

        # Extract user-assistant pairs
        pairs = []
        i = 0
        while i < len(messages):
            if messages[i].get('role') == 'user':
                user_content = messages[i].get('content', '')

                # Skip tool_result messages
                is_tool_result = False
                if isinstance(user_content, list):
                    is_tool_result = any(
                        isinstance(item, dict) and item.get('type') == 'tool_result'
                        for item in user_content
                    )
                if is_tool_result:
                    i += 1
                    continue

                # Extract user text
                user_text = self._extract_text(user_content)
                if len(user_text) < 5:
                    i += 1
                    continue

                # Collect consecutive assistant messages
                assistant_parts = []
                j = i + 1
                while j < len(messages):
                    if messages[j].get('role') == 'user':
                        uc = messages[j].get('content', '')
                        if isinstance(uc, list) and any(
                            isinstance(it, dict) and it.get('type') == 'tool_result'
                            for it in uc
                        ):
                            j += 1
                            continue
                        break
                    elif messages[j].get('role') == 'assistant':
                        assistant_parts.append(self._extract_text(messages[j].get('content', '')))
                    j += 1

                assistant_text = '\n'.join(assistant_parts)
                if len(assistant_text) < 5:
                    i = j
                    continue

                # Project name from parent directory
                encoded_dir = path.parent.name
                real_path = self._decode_claude_dir(encoded_dir)
                project_name = Path(real_path).name.lower() if real_path else encoded_dir.split('-')[-1].lower()

                # Project filter: skip entire transcript if project doesn't match
                if self.project_filter and project_name != self.project_filter:
                    i = j
                    continue

                # Timestamp
                timestamp = ""
                if messages[i].get('timestamp'):
                    ts_val = messages[i]['timestamp']
                    if isinstance(ts_val, str):
                        timestamp = ts_val
                    elif isinstance(ts_val, (int, float)):
                        timestamp = datetime.fromtimestamp(ts_val).isoformat()

                pair = ConversationPair(
                    user_message=user_text,
                    assistant_message=assistant_text,
                    project_name=project_name,
                    session_id=path.stem,
                    timestamp=timestamp,
                    source_tag="claude-code"
                )

                if not self.state.is_saved(pair.content_hash):
                    pairs.append(pair)

                i = j
            else:
                i += 1

        return pairs

    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        parts.append(item.get('text', ''))
                    elif item.get('type') == 'thinking':
                        thinking = item.get('thinking', '')
                        if thinking:
                            parts.append(f"[Thinking: {thinking[:200]}...]")
            return '\n'.join(parts)
        return str(content)


# ---------------------------------------------------------------------------
# Codebuff source
# ---------------------------------------------------------------------------

class CodebuffSource(BaseSourceWatcher):
    """Watches ~/.config/manicode/projects/ for chat-messages.json files."""

    POLL_INTERVAL = 30

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 projects_dir: str = None, project_filter: Optional[str] = None):
        super().__init__(state, api_url, dry_run, project_filter)
        self.projects_dir = Path(
            projects_dir or get_settings().CODEBUFF_DIR or os.getenv("CODEBUFF_PROJECTS_DIR",
                                       str(Path.home() / ".config" / "manicode" / "projects"))
        )

    async def poll(self) -> List[ConversationPair]:
        if not self.projects_dir.exists():
            return []

        pairs = []
        src_state = self.state.get_source_state("codebuff")

        # Scan all project directories
        for project_dir in sorted(self.projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            project_name = self._extract_project_name(str(project_dir))

            # Project filter: skip entire directory if it doesn't match
            if self.project_filter and project_name != self.project_filter:
                continue

            chats_dir = project_dir / "chats"

            if not chats_dir.exists():
                continue

            # Scan all chat sessions
            for chat_dir in sorted(chats_dir.iterdir()):
                if not chat_dir.is_dir():
                    continue

                chat_file = chat_dir / "chat-messages.json"
                if not chat_file.exists():
                    continue

                # Check for new content
                file_key = str(chat_file)
                last_mtime = src_state.get(file_key, 0)
                current_mtime = chat_file.stat().st_mtime

                if current_mtime <= last_mtime:
                    continue  # No changes

                try:
                    new_pairs = self._parse_chat(chat_file, project_name, chat_dir.name)
                    pairs.extend(new_pairs)
                    src_state[file_key] = current_mtime
                except Exception as e:
                    logger.warning("parse_error", source="codebuff", file=str(chat_file), error=str(e))

        self.state.set_source_state("codebuff", src_state)
        return pairs

    def _parse_chat(self, path: Path, project_name: str,
                    session_id: str) -> List[ConversationPair]:
        # Extract date from chat directory name (e.g., "2026-04-15T20-13-58.496Z")
        # Codebuff stores chat sessions in dirs named with ISO timestamp
        chat_date = ""
        try:
            # session_id is the directory name under chats/
            # Format: YYYY-MM-DDTHH-MM-SS.mmmZ — extract date part (first 10 chars)
            chat_date = session_id[:10]  # "2026-04-15"
        except Exception:
            pass
        with open(path, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        if not isinstance(messages, list):
            return []

        pairs = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.get('variant') == 'user':
                user_text = msg.get('content', '')
                if not isinstance(user_text, str) or len(user_text) < 5:
                    i += 1
                    continue

                # Collect consecutive AI messages
                assistant_parts = []
                j = i + 1
                while j < len(messages) and messages[j].get('variant') == 'ai':
                    ai_msg = messages[j]
                    # AI text is in blocks, not in content directly
                    blocks = ai_msg.get('blocks', [])
                    if blocks:
                        for block in blocks:
                            if isinstance(block, dict):
                                btype = block.get('type', '')
                                bcontent = block.get('content', '')
                                if btype == 'text' and isinstance(bcontent, str) and len(bcontent) >= 5:
                                    assistant_parts.append(bcontent)
                                elif btype == 'tool':
                                    # Include tool calls briefly
                                    tool_name = block.get('name', block.get('toolName', ''))
                                    if tool_name:
                                        assistant_parts.append(f"[Tool: {tool_name}]")
                    elif ai_msg.get('content') and isinstance(ai_msg['content'], str) and len(ai_msg['content']) >= 5:
                        assistant_parts.append(ai_msg['content'])
                    j += 1

                assistant_text = '\n'.join(assistant_parts)
                if len(assistant_text) < 5:
                    i = j
                    continue

                # Timestamp - Codebuff uses "HH:MM AM/PM" format in messages
                # but the actual date is in the chat directory name
                timestamp = ""
                ts_raw = msg.get('timestamp', '')
                if ts_raw and isinstance(ts_raw, str) and chat_date:
                    try:
                        dt = datetime.strptime(f"{chat_date} {ts_raw}", "%Y-%m-%d %I:%M %p")
                        timestamp = dt.isoformat()
                    except (ValueError, TypeError):
                        timestamp = f"{chat_date}T{ts_raw}"
                elif chat_date:
                    timestamp = f"{chat_date}T00:00:00"

                pair = ConversationPair(
                    user_message=user_text,
                    assistant_message=assistant_text,
                    project_name=project_name,
                    session_id=f"codebuff-{session_id}",
                    timestamp=timestamp,
                    source_tag="codebuff"
                )

                if not self.state.is_saved(pair.content_hash):
                    pairs.append(pair)

                i = j
            else:
                i += 1

        return pairs


# ---------------------------------------------------------------------------
# OpenCode source
# ---------------------------------------------------------------------------

class OpenCodeSource(BaseSourceWatcher):
    """Watches ~/.local/share/opencode/opencode.db (SQLite) for conversations."""

    POLL_INTERVAL = 15  # SQLite queries are very fast

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 db_path: str = None, project_filter: Optional[str] = None):
        super().__init__(state, api_url, dry_run, project_filter)
        self.db_path = Path(
            db_path or os.getenv("OPENCODE_DB_PATH",
                                 str(Path.home() / ".local" / "share" / "opencode" / "opencode.db"))
        )

    async def poll(self) -> List[ConversationPair]:
        if not self.db_path.exists():
            return []

        pairs = []
        src_state = self.state.get_source_state("opencode")
        last_msg_id = src_state.get("last_message_id", "")

        try:
            new_pairs = self._query_new_messages(last_msg_id)
            pairs.extend(new_pairs)

            # Update cursor
            if new_pairs:
                # Get the max message ID we processed
                max_id = self._get_max_message_id()
                if max_id:
                    src_state["last_message_id"] = max_id

        except Exception as e:
            logger.warning("sqlite_query_error", source="opencode", error=str(e))

        self.state.set_source_state("opencode", src_state)
        return pairs

    def _get_max_message_id(self) -> Optional[str]:
        """Get the latest message ID from the database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("SELECT id FROM message ORDER BY time_created DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

    # Batch size for IN clauses (SQLite limit is 999 on older versions)
    _BATCH_SIZE = 500

    def _query_new_messages(self, since_id: str) -> List[ConversationPair]:
        """Query new messages from SQLite since the given message ID."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row

            # Get sessions with project paths
            # OpenCode stores project path in the `project` table, not in `session`.
            # session has a foreign key to project.
            sessions = {}
            try:
                # Try joined query first (correct schema)
                # Use aliases so row['id'] and row['project_path'] work consistently
                rows = conn.execute(
                    "SELECT s.id as id, p.path as project_path FROM session s "
                    "LEFT JOIN project p ON s.project_id = p.id"
                ).fetchall()
                for row in rows:
                    sessions[row['id']] = row['project_path'] or ''
            except Exception:
                # Fallback: try project_path column directly (older schema)
                try:
                    rows = conn.execute("SELECT id, project_path FROM session").fetchall()
                    for row in rows:
                        sessions[row['id']] = row['project_path'] or ''
                except Exception:
                    pass

            # NOTE: OpenCode stores 'role' inside the data JSON blob, not as a column.
            # We use json_extract(data, '$.role') to get the role.
            _MSG_COLS = "id, session_id, json_extract(data, '$.role') as role, data"

            # Build query for new messages
            if since_id:
                # Get messages after the cursor
                # Use time_created to find messages newer than cursor
                cursor_row = conn.execute(
                    "SELECT time_created FROM message WHERE id = ?", (since_id,)
                ).fetchone()
                if cursor_row:
                    since_time = cursor_row['time_created']
                    msg_rows = conn.execute(
                        f"SELECT {_MSG_COLS} FROM message "
                        "WHERE time_created > ? ORDER BY time_created ASC",
                        (since_time,)
                    ).fetchall()
                else:
                    # Cursor not found — start from scratch with limit
                    msg_rows = conn.execute(
                        f"SELECT {_MSG_COLS} FROM message "
                        "ORDER BY time_created DESC LIMIT 500"
                    ).fetchall()
                    msg_rows.reverse()  # Process in chronological order
            else:
                # First run: only fetch the most recent 500 messages to avoid OOM
                msg_rows = conn.execute(
                    f"SELECT {_MSG_COLS} FROM message "
                    "ORDER BY time_created DESC LIMIT 500"
                ).fetchall()
                msg_rows.reverse()  # Process in chronological order

            # Group messages by session
            session_messages: Dict[str, List[Dict]] = {}
            for row in msg_rows:
                sid = row['session_id']
                # role comes from json_extract — may be None if data is malformed
                role = row['role']
                data = json.loads(row['data']) if row['data'] else {}
                if not role:
                    role = data.get('role', 'unknown')
                session_messages.setdefault(sid, []).append({
                    'id': row['id'],
                    'role': role,
                    'data': data,
                })

            # Extract pairs from each session
            pairs = []
            for sid, messages in session_messages.items():
                project_path = sessions.get(sid, '')
                project_name = Path(project_path).name.lower() if project_path else "opencode"

                # Project filter: skip entire session if project doesn't match
                if self.project_filter and project_name != self.project_filter:
                    continue

                # For each session, get text parts
                session_pairs = self._extract_session_pairs(
                    conn, sid, messages, project_name
                )
                pairs.extend(session_pairs)

            return pairs
        finally:
            conn.close()

    def _extract_session_pairs(
        self, conn, session_id: str, messages: List[Dict], project_name: str
    ) -> List[ConversationPair]:
        """Extract user-assistant pairs from a session's messages."""
        pairs = []

        # Get text parts for all messages in this session
        # Batch IN clauses to avoid SQLite parameter limits
        msg_ids = [m['id'] for m in messages]
        if not msg_ids:
            return []

        all_part_rows = []
        for batch_start in range(0, len(msg_ids), self._BATCH_SIZE):
            batch_ids = msg_ids[batch_start:batch_start + self._BATCH_SIZE]
            placeholders = ','.join(['?'] * len(batch_ids))
            part_rows = conn.execute(
                f"SELECT message_id, data FROM part "
                f"WHERE message_id IN ({placeholders}) "
                f"AND json_extract(data, '$.type') = 'text' "
                f"ORDER BY time_created ASC",
                batch_ids
            ).fetchall()
            all_part_rows.extend(part_rows)

        # Build message_id -> text map
        msg_texts: Dict[str, str] = {}
        for prow in all_part_rows:
            mid = prow['message_id']
            pdata = json.loads(prow['data']) if prow['data'] else {}
            text = pdata.get('text', '')
            if text:
                msg_texts.setdefault(mid, [])
                msg_texts[mid].append(text)

        # Extract user-assistant pairs
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg['role']
            msg_id = msg['id']
            data = msg.get('data', {})

            if role == 'user':
                user_parts = msg_texts.get(msg_id, [])
                user_text = '\n'.join(user_parts).strip()

                if len(user_text) < 5:
                    i += 1
                    continue

                # Collect consecutive assistant messages
                assistant_parts = []
                j = i + 1
                while j < len(messages) and messages[j]['role'] == 'assistant':
                    aid = messages[j]['id']
                    a_parts = msg_texts.get(aid, [])
                    a_text = '\n'.join(a_parts).strip()
                    if a_text and len(a_text) >= 5:
                        assistant_parts.append(a_text)
                    j += 1

                assistant_text = '\n'.join(assistant_parts)
                if len(assistant_text) < 5:
                    i = j
                    continue

                # Timestamp from message data
                timestamp = ""
                time_data = data.get('time', {})
                if isinstance(time_data, dict):
                    created = time_data.get('created')
                    if created and isinstance(created, (int, float)):
                        # Milliseconds since epoch
                        timestamp = datetime.fromtimestamp(created / 1000).isoformat()

                pair = ConversationPair(
                    user_message=user_text,
                    assistant_message=assistant_text,
                    project_name=project_name,
                    session_id=f"opencode-{session_id[:12]}",
                    timestamp=timestamp,
                    source_tag="opencode"
                )

                if not self.state.is_saved(pair.content_hash):
                    pairs.append(pair)

                i = j
            else:
                i += 1

        return pairs


# ---------------------------------------------------------------------------
# KiloCode source
# ---------------------------------------------------------------------------

class KiloCodeSource(BaseSourceWatcher):
    """Watches ~/.vscode[-server]/globalStorage/kilocode.kilo-code/tasks/ for conversations."""

    POLL_INTERVAL = 30

    # Possible storage paths
    STORAGE_PATHS = [
        Path.home() / ".vscode" / "globalStorage" / "kilocode.kilo-code",
        Path.home() / ".vscode-server" / "data" / "User" / "globalStorage" / "kilocode.kilo-code",
        # Also check for Roo Code
        Path.home() / ".vscode" / "globalStorage" / "roocode.roo-code",
        Path.home() / ".vscode-server" / "data" / "User" / "globalStorage" / "roocode.roo-code",
    ]

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 storage_dir: str = None, project_filter: Optional[str] = None):
        super().__init__(state, api_url, dry_run, project_filter)
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = self._detect_storage_dir()

    def _detect_storage_dir(self) -> Optional[Path]:
        """Find the KiloCode/RooCode storage directory."""
        for path in self.STORAGE_PATHS:
            if path.exists():
                return path
        return None

    async def poll(self) -> List[ConversationPair]:
        if not self.storage_dir or not self.storage_dir.exists():
            return []

        pairs = []
        src_state = self.state.get_source_state("kilocode")
        tasks_dir = self.storage_dir / "tasks"

        if not tasks_dir.exists():
            return []

        # Scan task directories
        for task_dir in sorted(tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue

            history_file = task_dir / "api_conversation_history.json"
            if not history_file.exists():
                continue

            # Check for modifications
            file_key = str(history_file)
            last_mtime = src_state.get(file_key, 0)
            current_mtime = history_file.stat().st_mtime

            if current_mtime <= last_mtime:
                continue

            try:
                new_pairs = self._parse_history(history_file, task_dir.name)
                pairs.extend(new_pairs)
                src_state[file_key] = current_mtime
            except Exception as e:
                logger.warning("parse_error", source="kilocode", file=str(history_file), error=str(e))

        self.state.set_source_state("kilocode", src_state)
        return pairs

    def _parse_history(self, path: Path, task_id: str) -> List[ConversationPair]:
        """Parse KiloCode/RooCode api_conversation_history.json."""
        with open(path, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        if not isinstance(messages, list):
            return []

        # Try to detect project name from task metadata
        project_name = self._detect_project_from_task(path.parent)
        if not project_name:
            project_name = "kilocode"

        pairs = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.get('role', '')

            if role == 'user':
                user_text = self._extract_blocks(msg.get('content', []))
                if len(user_text) < 5:
                    i += 1
                    continue

                # Collect consecutive assistant messages
                assistant_parts = []
                j = i + 1
                while j < len(messages) and messages[j].get('role') == 'assistant':
                    a_text = self._extract_blocks(messages[j].get('content', []))
                    if a_text and len(a_text) >= 5:
                        assistant_parts.append(a_text)
                    j += 1

                assistant_text = '\n'.join(assistant_parts)
                if len(assistant_text) < 5:
                    i = j
                    continue

                # Timestamp
                timestamp = msg.get('ts', '')
                if not isinstance(timestamp, str):
                    timestamp = ""

                pair = ConversationPair(
                    user_message=user_text,
                    assistant_message=assistant_text,
                    project_name=project_name,
                    session_id=f"kilocode-{task_id[:12]}",
                    timestamp=timestamp,
                    source_tag="kilocode"
                )

                if not self.state.is_saved(pair.content_hash):
                    pairs.append(pair)

                i = j
            else:
                i += 1

        return pairs

    # RooCode/KiloCode XML metadata tags to filter out
    _FILTER_XML_TAGS = [
        '<environment_details>', '<task>', '<feedback>',
        '<attempt_completion>', '<ask_followup_question>',
        '<new_task_created>', '<task_completed>',
    ]

    def _extract_blocks(self, content) -> str:
        """Extract text from KiloCode content blocks."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    # Standard text block: {"type": "text", "text": "..."}
                    if block.get('type') == 'text':
                        text = block.get('text', '')
                        # Skip XML metadata blocks injected by RooCode/KiloCode
                        if any(tag in text for tag in self._FILTER_XML_TAGS):
                            continue
                        if text:
                            parts.append(text)
                    # Tool use block
                    elif block.get('type') == 'tool_use':
                        tool_name = block.get('name', '')
                        if tool_name:
                            parts.append(f"[Tool: {tool_name}]")
            return '\n'.join(parts)
        return str(content) if content else ""

    def _detect_project_from_task(self, task_dir: Path) -> str:
        """Try to detect project name from task metadata."""
        # Check for task metadata file
        meta_file = task_dir / "task.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                # Various possible fields for project/cwd
                for key in ('cwd', 'workspace', 'projectPath', 'rootPath'):
                    val = meta.get(key, '')
                    if val and isinstance(val, str):
                        return Path(val).name.lower()
            except Exception:
                pass

        # Check for claude_messages or other files that might have project info
        for f in task_dir.iterdir():
            if f.name.endswith('.json') and f.name != 'api_conversation_history.json':
                try:
                    data = json.loads(f.read_text())
                    if isinstance(data, dict):
                        for key in ('cwd', 'workspace', 'projectPath', 'rootPath'):
                            val = data.get(key, '')
                            if val and isinstance(val, str):
                                return Path(val).name.lower()
                except Exception:
                    continue

        return ""


# ---------------------------------------------------------------------------
# Multi-Source Watcher Daemon
# ---------------------------------------------------------------------------

class MultiSourceWatcher:
    """Orchestrates multiple source watchers."""

    def __init__(
        self,
        sources: List[BaseSourceWatcher],
        state: WatcherState,
        dry_run: bool = False,
    ):
        self.sources = sources
        self.state = state
        self.dry_run = dry_run
        self.shutdown = False
        self.stats = {
            "total_saved": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "start_time": time.time(),
        }

    async def run_source(self, source: BaseSourceWatcher):
        """Run a single source's polling loop."""
        logger.info("source_starting", source=source.name, interval=source.POLL_INTERVAL)
        while not self.shutdown:
            try:
                pairs = await source.poll()
                if pairs:
                    logger.info("new_pairs_found", source=source.name, count=len(pairs))
                    for pair in pairs:
                        success = await source.save_pair(pair)
                        if success:
                            self.stats["total_saved"] += 1
                        else:
                            self.stats["total_skipped"] += 1

                    # Save state after each batch
                    self.state.save()

            except Exception as e:
                logger.error("poll_error", source=source.name, error=str(e))
                self.stats["total_errors"] += 1

            await asyncio.sleep(source.POLL_INTERVAL)

    async def run_once(self):
        """Run a single poll cycle for each source and exit."""
        logger.info("watcher_starting", mode="single_poll",
                     sources=[s.name for s in self.sources],
                     dry_run=self.dry_run)

        for source in self.sources:
            await source.ensure_session()
            try:
                pairs = await source.poll()
                logger.info("poll_result", source=source.name, new_pairs=len(pairs))
                for pair in pairs[:5]:  # Show first 5
                    logger.info("pair_preview",
                                source_tag=pair.source_tag,
                                project=pair.project_name,
                                user_preview=pair.user_message[:60],
                                hash=pair.content_hash)
                if len(pairs) > 5:
                    logger.info("more_pairs", count=len(pairs) - 5)

                for pair in pairs:
                    success = await source.save_pair(pair)
                    if success:
                        self.stats["total_saved"] += 1
                    else:
                        self.stats["total_skipped"] += 1
            except Exception as e:
                logger.error("poll_error", source=source.name, error=str(e))
                self.stats["total_errors"] += 1

            await source.close_session()

        self.state.save()
        logger.info("poll_complete",
                     saved=self.stats['total_saved'],
                     skipped=self.stats['total_skipped'],
                     errors=self.stats['total_errors'])

    async def run(self):
        """Run all source watchers concurrently."""
        logger.info("watcher_starting", mode="daemon",
                     sources=[s.name for s in self.sources],
                     dry_run=self.dry_run)

        for source in self.sources:
            logger.info("source_polling", source=source.name, interval=source.POLL_INTERVAL)

        # Run all sources concurrently
        tasks = [asyncio.create_task(self.run_source(s)) for s in self.sources]

        try:
            while not self.shutdown:
                await asyncio.sleep(5)
                # Periodic stats
                if int(time.time()) % 60 == 0:
                    elapsed = int(time.time() - self.stats["start_time"])
                    logger.info("periodic_stats",
                                 saved=self.stats['total_saved'],
                                 skipped=self.stats['total_skipped'],
                                 errors=self.stats['total_errors'],
                                 uptime=elapsed)
                    self.state.save()
        except KeyboardInterrupt:
            logger.info("shutdown_signal")
            self.shutdown = True

        # Cleanup
        for task in tasks:
            task.cancel()
        for source in self.sources:
            await source.close_session()
        self.state.save()
        logger.info("daemon_stopped")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_sources(args, state: WatcherState) -> List[BaseSourceWatcher]:
    """Build source watchers based on CLI args."""
    api_url = args.api_url
    dry_run = args.dry_run
    source_filter = args.source.lower() if args.source else None
    project_filter = args.project_filter or get_settings().ACTIVE_PROJECT

    if project_filter:
        logger.info("project_filter_enabled", project=project_filter.lower())

    sources = []

    # Claude Code
    if not source_filter or source_filter == "claude-code":
        s = ClaudeCodeSource(state, api_url, dry_run, args.claude_dir, project_filter)
        if s.projects_dir.exists():
            sources.append(s)
        else:
            logger.info("source_skip", source="claude-code", reason="directory_not_found", path=str(s.projects_dir))

    # Codebuff
    if not source_filter or source_filter == "codebuff":
        s = CodebuffSource(state, api_url, dry_run, args.codebuff_dir, project_filter)
        if s.projects_dir.exists():
            sources.append(s)
        else:
            logger.info("source_skip", source="codebuff", reason="directory_not_found", path=str(s.projects_dir))

    # OpenCode
    if not source_filter or source_filter == "opencode":
        s = OpenCodeSource(state, api_url, dry_run, args.opencode_db, project_filter)
        if s.db_path.exists():
            sources.append(s)
        else:
            logger.info("source_skip", source="opencode", reason="db_not_found", path=str(s.db_path))

    # KiloCode
    if not source_filter or source_filter == "kilocode":
        s = KiloCodeSource(state, api_url, dry_run, args.kilocode_dir, project_filter)
        if s.storage_dir and s.storage_dir.exists():
            sources.append(s)
        else:
            logger.info("source_skip", source="kilocode", reason="storage_dir_not_found")

    return sources


def main():
    parser = argparse.ArgumentParser(
        description="MnemoLite Multi-Source Conversation Watcher"
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Only watch one source: claude-code, codebuff, opencode, kilocode"
    )
    parser.add_argument(
        "--api-url", type=str, default="http://localhost:8001",
        help="MnemoLite API URL (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview pairs without saving to API"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single poll cycle and exit (useful for testing)"
    )
    parser.add_argument(
        "--state-file", type=str, default=None,
        help="State file path (default: ~/.local/share/mnemo/multi-watcher-state.json)"
    )
    parser.add_argument("--claude-dir", type=str, default=None,
                        help="Custom Claude Code projects directory")
    parser.add_argument("--codebuff-dir", type=str, default=None,
                        help="Custom Codebuff projects directory")
    parser.add_argument("--opencode-db", type=str, default=None,
                        help="Custom OpenCode SQLite DB path")
    parser.add_argument("--kilocode-dir", type=str, default=None,
                        help="Custom KiloCode storage directory")
    parser.add_argument("--project-filter", type=str, default=None,
                        help="Only import conversations for this project (e.g. 'mnemolite'). "
                             "Also set via ACTIVE_PROJECT env var. Without this, all projects are imported.")

    args = parser.parse_args()

    # Load state (None lets WatcherState use its default path)
    state = WatcherState(args.state_file)

    # Build sources
    sources = build_sources(args, state)

    if not sources:
        logger.error("no_sources_available")
        sys.exit(1)

    # Run daemon or single poll
    daemon = MultiSourceWatcher(sources, state, dry_run=args.dry_run)

    # Signal handlers
    def signal_handler(sig, frame):
        daemon.shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.once:
        asyncio.run(daemon.run_once())
    else:
        asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
