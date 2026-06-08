"""
Tests for the MnemoLite Multi-Source Conversation Watcher Daemon.

Tests the 4 source parsers (ClaudeCodeSource, CodebuffSource, OpenCodeSource,
KiloCodeSource) plus WatcherState and ConversationPair utilities.

Uses only local fixtures (tmp_path, temp SQLite DBs) — no external services.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import from the daemon script
# ---------------------------------------------------------------------------
import importlib.util
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# The daemon script has a top-level `sys.exit(1)` if aiohttp is missing.
# For unit tests that don't need aiohttp, we mock it before import.
if "aiohttp" not in sys.modules:
    sys.modules["aiohttp"] = MagicMock()

# The script filename uses hyphens (multi-watcher-daemon.py) which is
# not a valid Python identifier. Use importlib to load it.
_mod_path = os.path.join(_project_root, "scripts", "multi-watcher-daemon.py")
_spec = importlib.util.spec_from_file_location("multi_watcher_daemon", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["multi_watcher_daemon"] = _mod
_spec.loader.exec_module(_mod)

ConversationPair = _mod.ConversationPair
WatcherState = _mod.WatcherState
BaseSourceWatcher = _mod.BaseSourceWatcher
ClaudeCodeSource = _mod.ClaudeCodeSource
CodebuffSource = _mod.CodebuffSource
OpenCodeSource = _mod.OpenCodeSource
KiloCodeSource = _mod.KiloCodeSource



# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def state(tmp_path):
    """WatcherState with a temp state file."""
    state_file = tmp_path / "test-state.json"
    return WatcherState(str(state_file))


@pytest.fixture
def api_url():
    return "http://localhost:9999"


# ===========================================================================
# ConversationPair
# ===========================================================================


class TestConversationPair:
    def test_content_hash_deterministic(self):
        pair = ConversationPair(
            user_message="hello",
            assistant_message="world",
            project_name="test",
            session_id="s1",
            timestamp="",
            source_tag="test",
        )
        assert pair.content_hash == pair.content_hash
        assert len(pair.content_hash) == 16

    def test_content_hash_differs_for_different_content(self):
        p1 = ConversationPair("hello", "world", "p", "s", "", "t")
        p2 = ConversationPair("hello", "different", "p", "s", "", "t")
        assert p1.content_hash != p2.content_hash

    def test_content_hash_same_for_same_content(self):
        p1 = ConversationPair("hello", "world", "p", "s", "", "t")
        p2 = ConversationPair("hello", "world", "p", "s", "", "t")
        assert p1.content_hash == p2.content_hash


# ===========================================================================
# WatcherState
# ===========================================================================


class TestWatcherState:
    def test_initial_state_empty(self, tmp_path):
        state = WatcherState(str(tmp_path / "new-state.json"))
        assert state.state == {"sources": {}, "saved_hashes": [], "stats": {}}

    def test_mark_saved_and_is_saved(self, state):
        h = "abc123"
        assert not state.is_saved(h)
        state.mark_saved(h)
        assert state.is_saved(h)

    def test_mark_saved_twice_idempotent_lookup(self, state):
        """Calling mark_saved twice with the same hash should not break is_saved."""
        state.mark_saved("hash1")
        state.mark_saved("hash1")
        # The list may have duplicates, but set-based lookup is always correct
        assert state.is_saved("hash1")
        assert "hash1" in state._hash_set

    def test_save_and_reload(self, tmp_path):
        state_file = tmp_path / "persist-state.json"
        s1 = WatcherState(str(state_file))
        s1.mark_saved("h1")
        s1.mark_saved("h2")
        s1.save()

        s2 = WatcherState(str(state_file))
        assert s2.is_saved("h1")
        assert s2.is_saved("h2")

    def test_get_set_source_state(self, state):
        ss = state.get_source_state("claude-code")
        assert ss == {}
        state.set_source_state("claude-code", {"last_id": "123"})
        ss2 = state.get_source_state("claude-code")
        assert ss2["last_id"] == "123"

    def test_creates_parent_directory_on_save(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "state.json"
        state = WatcherState(str(nested))
        state.mark_saved("x")
        state.save()
        assert nested.exists()

    def test_hash_set_caching(self, state):
        """Verify that _cached_hash_set is maintained across mark_saved calls."""
        state.mark_saved("h1")
        assert "h1" in state._hash_set
        state.mark_saved("h2")
        assert "h2" in state._hash_set


# ===========================================================================
# BaseSourceWatcher
# ===========================================================================


class TestBaseSourceWatcher:
    def test_extract_project_name(self, state, api_url):
        watcher = ClaudeCodeSource(state, api_url)
        assert watcher._extract_project_name("/home/user/MnemoLite") == "mnemolite"
        assert watcher._extract_project_name("/home/user/My Project") == "my project"

    def test_decode_claude_dir_standard(self, state, api_url):
        watcher = ClaudeCodeSource(state, api_url)
        result = watcher._decode_claude_dir("-home-giak-Work-MnemoLite")
        assert result == "/home/giak/Work/MnemoLite"

    def test_decode_claude_dir_projects(self, state, api_url):
        watcher = ClaudeCodeSource(state, api_url)
        result = watcher._decode_claude_dir("-home-giak-projects-myapp")
        assert result == "/home/giak/projects/myapp"

    def test_decode_claude_dir_unknown_format(self, state, api_url):
        watcher = ClaudeCodeSource(state, api_url)
        result = watcher._decode_claude_dir("some-other-format")
        assert result == ""


# ===========================================================================
# ClaudeCodeSource
# ===========================================================================


class TestClaudeCodeSource:
    def _make_transcript(self, tmp_path, encoded_dir, messages_data):
        """Create a fake Claude Code JSONL transcript file."""
        dir_path = tmp_path / ".claude" / "projects" / encoded_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        # Ensure file is old enough to pass the 60s cooldown
        transcript = dir_path / "session-abc123.jsonl"
        lines = []
        for msg in messages_data:
            lines.append(json.dumps({"message": msg}))
        transcript.write_text("\n".join(lines))
        # Set mtime to the past to pass the cooldown check
        old_time = time.time() - 120
        os.utime(str(transcript), (old_time, old_time))
        return transcript

    @pytest.mark.asyncio
    async def test_poll_empty_dir(self, tmp_path, state, api_url):
        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / "nonexistent"))
        pairs = await source.poll()
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_finds_pairs(self, tmp_path, state, api_url):
        messages = [
            {"role": "user", "content": "Please explain decorators", "timestamp": "2025-01-15T10:00:00"},
            {"role": "assistant", "content": "Decorators are a powerful feature..."},
            {"role": "user", "content": "Can you show an example?", "timestamp": "2025-01-15T10:01:00"},
            {"role": "assistant", "content": "Sure! Here is a simple decorator example."},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-MyProject", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 2
        assert pairs[0].user_message == "Please explain decorators"
        assert pairs[0].source_tag == "claude-code"
        assert pairs[0].project_name == "myproject"
        assert pairs[0].timestamp == "2025-01-15T10:00:00"

    @pytest.mark.asyncio
    async def test_poll_skips_tool_result_user_messages(self, tmp_path, state, api_url):
        messages = [
            {"role": "user", "content": "What does this function do?"},
            {"role": "assistant", "content": "It computes the factorial."},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "file contents..."}
            ]},
            {"role": "assistant", "content": "Now I can see the file."},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-Proj", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        # Only 1 pair — the tool_result user message is skipped
        assert len(pairs) == 1
        assert pairs[0].user_message == "What does this function do?"

    @pytest.mark.asyncio
    async def test_poll_skips_short_messages(self, tmp_path, state, api_url):
        messages = [
            {"role": "user", "content": "Hi"},  # < 5 chars, skipped
            {"role": "assistant", "content": "Ok"},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-Proj", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_poll_skips_unchanged_files(self, tmp_path, state, api_url):
        messages = [
            {"role": "user", "content": "Hello world query", "timestamp": "2025-01-15T10:00:00"},
            {"role": "assistant", "content": "Hello world response"},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-Proj", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        # First poll: finds the pair
        pairs1 = await source.poll()
        assert len(pairs1) == 1
        # Mark as saved (simulates save_pair)
        state.mark_saved(pairs1[0].content_hash)
        # Second poll: same file, no size change, should return nothing
        pairs2 = await source.poll()
        assert len(pairs2) == 0

    def test_extract_text_string(self, state, api_url):
        source = ClaudeCodeSource(state, api_url)
        assert source._extract_text("plain text") == "plain text"

    def test_extract_text_blocks(self, state, api_url):
        source = ClaudeCodeSource(state, api_url)
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "thinking", "thinking": "I should respond politely"},
            {"type": "text", "text": "World"},
        ]
        result = source._extract_text(content)
        assert "Hello" in result
        assert "World" in result
        assert "[Thinking:" in result

    def test_extract_text_empty_list(self, state, api_url):
        source = ClaudeCodeSource(state, api_url)
        assert source._extract_text([]) == ""

    @pytest.mark.asyncio
    async def test_poll_handles_list_user_content_text_blocks(self, tmp_path, state, api_url):
        """Claude Code user messages with list content (text blocks, not tool_result)."""
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Please explain this function"}
            ], "timestamp": "2025-06-01T10:00:00"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "This function handles data validation."}
            ]},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-Proj", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].user_message == "Please explain this function"
        assert "data validation" in pairs[0].assistant_message

    @pytest.mark.asyncio
    async def test_poll_handles_integer_timestamp(self, tmp_path, state, api_url):
        """Claude Code integer timestamps should be converted to ISO format."""
        messages = [
            {"role": "user", "content": "What time is it now?", "timestamp": 1735689600},
            {"role": "assistant", "content": "The current time has been noted."},
        ]
        self._make_transcript(tmp_path, "-home-user-Work-Proj", messages)

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].timestamp != ""
        # Should be an ISO format string
        assert "T" in pairs[0].timestamp

    @pytest.mark.asyncio
    async def test_poll_skips_agent_files(self, tmp_path, state, api_url):
        """Files starting with 'agent-' should be skipped."""
        dir_path = tmp_path / ".claude" / "projects" / "-home-user-Work-Proj"
        dir_path.mkdir(parents=True, exist_ok=True)

        # Normal file
        normal = dir_path / "session-1.jsonl"
        normal.write_text(json.dumps({"message": {
            "role": "user", "content": "Normal query here please", "timestamp": ""
        }}) + "\n" + json.dumps({"message": {
            "role": "assistant", "content": "Normal response goes here"
        }}))

        # Agent file — should be skipped
        agent = dir_path / "agent-session-2.jsonl"
        agent.write_text(json.dumps({"message": {
            "role": "user", "content": "Agent query should be ignored", "timestamp": ""
        }}) + "\n" + json.dumps({"message": {
            "role": "assistant", "content": "Agent response should be ignored"
        }}))

        # Make files old enough
        old_time = time.time() - 120
        os.utime(str(normal), (old_time, old_time))
        os.utime(str(agent), (old_time, old_time))

        source = ClaudeCodeSource(state, api_url, projects_dir=str(tmp_path / ".claude" / "projects"))
        pairs = await source.poll()
        # Only the normal file produces a pair
        assert len(pairs) == 1
        assert "Normal query" in pairs[0].user_message


# ===========================================================================
# CodebuffSource
# ===========================================================================


class TestCodebuffSource:
    def _make_chat(self, tmp_path, project_name, chat_dir_name, messages_data):
        """Create a fake Codebuff chat-messages.json file."""
        chat_dir = tmp_path / ".config" / "manicode" / "projects" / project_name / "chats" / chat_dir_name
        chat_dir.mkdir(parents=True, exist_ok=True)
        chat_file = chat_dir / "chat-messages.json"
        chat_file.write_text(json.dumps(messages_data))
        return chat_file

    @pytest.mark.asyncio
    async def test_poll_empty_dir(self, tmp_path, state, api_url):
        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / "nonexistent"))
        pairs = await source.poll()
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_finds_pairs(self, tmp_path, state, api_url):
        messages = [
            {"variant": "user", "content": "How do I use pytest fixtures?", "timestamp": "10:30 AM"},
            {"variant": "ai", "blocks": [
                {"type": "text", "content": "Pytest fixtures are reusable test components..."},
            ]},
        ]
        self._make_chat(tmp_path, "MnemoLite", "2026-04-15T10-13-58.496Z", messages)

        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / ".config" / "manicode" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].user_message == "How do I use pytest fixtures?"
        assert "Pytest fixtures" in pairs[0].assistant_message
        assert pairs[0].source_tag == "codebuff"
        assert pairs[0].project_name == "mnemolite"
        # Timestamp should include the date from the directory name
        assert "2026-04-15" in pairs[0].timestamp

    @pytest.mark.asyncio
    async def test_poll_multiple_ai_blocks(self, tmp_path, state, api_url):
        messages = [
            {"variant": "user", "content": "Explain decorators", "timestamp": "02:15 PM"},
            {"variant": "ai", "blocks": [
                {"type": "text", "content": "Decorators wrap functions..."},
                {"type": "tool", "name": "read_file", "content": ""},
                {"type": "text", "content": "As you can see from the file..."},
            ]},
        ]
        self._make_chat(tmp_path, "MyProject", "2026-05-01T14-15-00.000Z", messages)

        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / ".config" / "manicode" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert "Decorators wrap functions" in pairs[0].assistant_message
        assert "[Tool: read_file]" in pairs[0].assistant_message
        assert "As you can see" in pairs[0].assistant_message

    @pytest.mark.asyncio
    async def test_poll_skips_short_messages(self, tmp_path, state, api_url):
        messages = [
            {"variant": "user", "content": "Ok"},  # < 5 chars
            {"variant": "ai", "blocks": [{"type": "text", "content": "Sure!"}]},
        ]
        self._make_chat(tmp_path, "Proj", "2026-01-01T00-00-00.000Z", messages)

        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / ".config" / "manicode" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_poll_ignores_already_seen(self, tmp_path, state, api_url):
        messages = [
            {"variant": "user", "content": "First question here", "timestamp": "09:00 AM"},
            {"variant": "ai", "blocks": [{"type": "text", "content": "First answer response"}]},
        ]
        self._make_chat(tmp_path, "Proj", "2026-01-01T09-00-00.000Z", messages)

        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / ".config" / "manicode" / "projects"))

        # First poll finds the pair
        pairs1 = await source.poll()
        assert len(pairs1) == 1

        # Second poll: mtime hasn't changed, should return nothing
        pairs2 = await source.poll()
        assert len(pairs2) == 0

    def test_parse_chat_date_from_dir_name(self, tmp_path, state, api_url):
        """Verify that the date is extracted from the chat directory name."""
        source = CodebuffSource(state, api_url)
        chat_dir = tmp_path / "test-project" / "chats" / "2026-03-20T15-30-00.000Z"
        chat_dir.mkdir(parents=True, exist_ok=True)
        chat_file = chat_dir / "chat-messages.json"
        chat_file.write_text(json.dumps([
            {"variant": "user", "content": "What time is it?", "timestamp": "03:30 PM"},
            {"variant": "ai", "blocks": [{"type": "text", "content": "It is 3:30 PM right now."}]},
        ]))

        pairs = source._parse_chat(chat_file, "testproject", "2026-03-20T15-30-00.000Z")
        assert len(pairs) == 1
        # The timestamp should contain the date from the directory name
        assert "2026-03-20" in pairs[0].timestamp

    def test_parse_chat_no_timestamp(self, tmp_path, state, api_url):
        """Messages without timestamps still get the directory date."""
        source = CodebuffSource(state, api_url)
        chat_dir = tmp_path / "proj" / "chats" / "2025-12-25T00-00-00.000Z"
        chat_dir.mkdir(parents=True, exist_ok=True)
        chat_file = chat_dir / "chat-messages.json"
        chat_file.write_text(json.dumps([
            {"variant": "user", "content": "Merry Christmas!"},
            {"variant": "ai", "blocks": [{"type": "text", "content": "Happy holidays to you too!"}]},
        ]))

        pairs = source._parse_chat(chat_file, "proj", "2025-12-25T00-00-00.000Z")
        assert len(pairs) == 1
        assert "2025-12-25" in pairs[0].timestamp

    @pytest.mark.asyncio
    async def test_poll_ai_content_without_blocks(self, tmp_path, state, api_url):
        """AI messages using 'content' field directly (no 'blocks' key)."""
        messages = [
            {"variant": "user", "content": "What is the output?", "timestamp": "11:00 AM"},
            {"variant": "ai", "content": "The output is 42."},
        ]
        self._make_chat(tmp_path, "TestProj", "2026-07-01T11-00-00.000Z", messages)

        source = CodebuffSource(state, api_url, projects_dir=str(tmp_path / ".config" / "manicode" / "projects"))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert "The output is 42" in pairs[0].assistant_message

    def test_parse_chat_invalid_json_structure(self, tmp_path, state, api_url):
        """Non-list JSON should return empty."""
        source = CodebuffSource(state, api_url)
        chat_dir = tmp_path / "proj" / "chats" / "2025-01-01T00-00-00.000Z"
        chat_dir.mkdir(parents=True, exist_ok=True)
        chat_file = chat_dir / "chat-messages.json"
        chat_file.write_text('{"not": "a list"}')

        pairs = source._parse_chat(chat_file, "proj", "2025-01-01T00-00-00.000Z")
        assert pairs == []


# ===========================================================================
# OpenCodeSource
# ===========================================================================


def _create_opencode_db(db_path: Path, sessions=None, messages=None, parts=None):
    """Create a minimal OpenCode SQLite DB for testing.

    Tables: project, session, message, part
    """
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS project (
            id TEXT PRIMARY KEY,
            name TEXT,
            path TEXT
        );
        CREATE TABLE IF NOT EXISTS session (
            id TEXT PRIMARY KEY,
            project_id TEXT REFERENCES project(id),
            time_created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS message (
            id TEXT PRIMARY KEY,
            session_id TEXT REFERENCES session(id),
            data TEXT DEFAULT '{}',
            time_created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS part (
            id TEXT PRIMARY KEY,
            message_id TEXT REFERENCES message(id),
            data TEXT DEFAULT '{}',
            time_created REAL DEFAULT 0
        );
    """)
    # Insert projects
    for p in (sessions or []):
        conn.execute(
            "INSERT OR IGNORE INTO project (id, name, path) VALUES (?, ?, ?)",
            (p.get("project_id", "proj1"), p.get("project_name", "proj"), p.get("project_path", "/home/user/proj"))
        )
    # Insert sessions
    for s in (sessions or []):
        conn.execute(
            "INSERT OR IGNORE INTO session (id, project_id, time_created) VALUES (?, ?, ?)",
            (s["id"], s.get("project_id", "proj1"), s.get("time_created", 1.0))
        )
    # Insert messages
    for m in (messages or []):
        conn.execute(
            "INSERT OR IGNORE INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
            (m["id"], m["session_id"], json.dumps(m.get("data", {})), m.get("time_created", 1.0))
        )
    # Insert parts
    for p in (parts or []):
        conn.execute(
            "INSERT OR IGNORE INTO part (id, message_id, data, time_created) VALUES (?, ?, ?, ?)",
            (p["id"], p["message_id"], json.dumps(p.get("data", {})), p.get("time_created", 1.0))
        )
    conn.commit()
    conn.close()


class TestOpenCodeSource:
    @pytest.mark.asyncio
    async def test_poll_db_not_found(self, tmp_path, state, api_url):
        source = OpenCodeSource(state, api_url, db_path=str(tmp_path / "nonexistent.db"))
        pairs = await source.poll()
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_finds_pairs(self, tmp_path, state, api_url):
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "/home/user/MnemoLite", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "How does async work?"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "Async uses event loops..."}, "time_created": 2.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].user_message == "How does async work?"
        assert pairs[0].assistant_message == "Async uses event loops..."
        assert pairs[0].source_tag == "opencode"
        assert pairs[0].project_name == "mnemolite"

    @pytest.mark.asyncio
    async def test_poll_skips_short_messages(self, tmp_path, state, api_url):
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "/home/user/proj", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "Hi"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "Ok"}, "time_created": 2.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))
        pairs = await source.poll()
        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_poll_uses_cursor(self, tmp_path, state, api_url):
        """Second poll should only find new messages after the cursor."""
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "/proj", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "First question here?"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "First answer goes here"}, "time_created": 2.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))

        # First poll
        pairs1 = await source.poll()
        assert len(pairs1) == 1

        # Add more messages to the DB
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
                     ("msg3", "sess1", json.dumps({"role": "user"}), 3.0))
        conn.execute("INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
                     ("msg4", "sess1", json.dumps({"role": "assistant"}), 4.0))
        conn.execute("INSERT INTO part (id, message_id, data, time_created) VALUES (?, ?, ?, ?)",
                     ("p3", "msg3", json.dumps({"type": "text", "text": "Second question here?"}), 3.0))
        conn.execute("INSERT INTO part (id, message_id, data, time_created) VALUES (?, ?, ?, ?)",
                     ("p4", "msg4", json.dumps({"type": "text", "text": "Second answer here!"}), 4.0))
        conn.commit()
        conn.close()

        # Second poll should only find the new messages
        pairs2 = await source.poll()
        assert len(pairs2) == 1
        assert "Second question" in pairs2[0].user_message

    @pytest.mark.asyncio
    async def test_poll_multiple_assistant_messages(self, tmp_path, state, api_url):
        """Consecutive assistant messages should be joined."""
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "/proj", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
                {"id": "msg3", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 3.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "Explain this code"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "This function computes..."}, "time_created": 2.0},
                {"id": "p3", "message_id": "msg3", "data": {"type": "text", "text": "And it also handles..."}, "time_created": 3.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert "This function computes" in pairs[0].assistant_message
        assert "And it also handles" in pairs[0].assistant_message

    @pytest.mark.asyncio
    async def test_poll_no_project_uses_opencode_default(self, tmp_path, state, api_url):
        """If no project path is found, default to 'opencode'."""
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "Question text here?"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "Answer text here!"}, "time_created": 2.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].project_name == "opencode"

    @pytest.mark.asyncio
    async def test_poll_cursor_prevents_rereading(self, tmp_path, state, api_url):
        """Cursor-based state prevents re-reading already processed messages."""
        db_path = tmp_path / "opencode.db"
        _create_opencode_db(
            db_path,
            sessions=[{"id": "sess1", "project_id": "proj1", "project_path": "/proj", "time_created": 1.0}],
            messages=[
                {"id": "msg1", "session_id": "sess1", "data": {"role": "user"}, "time_created": 1.0},
                {"id": "msg2", "session_id": "sess1", "data": {"role": "assistant"}, "time_created": 2.0},
            ],
            parts=[
                {"id": "p1", "message_id": "msg1", "data": {"type": "text", "text": "What is Python?"}, "time_created": 1.0},
                {"id": "p2", "message_id": "msg2", "data": {"type": "text", "text": "Python is a language."}, "time_created": 2.0},
            ],
        )

        source = OpenCodeSource(state, api_url, db_path=str(db_path))
        pairs = await source.poll()
        assert len(pairs) == 1

        # Mark as saved (simulates processing)
        state.mark_saved(pairs[0].content_hash)

        # Re-query with the same data — _query_new_messages returns fresh,
        # but is_saved filters them. However, the cursor prevents re-reading
        # the same messages. This test verifies the cursor mechanism.
        pairs2 = await source.poll()
        assert len(pairs2) == 0  # Cursor already past these messages


# ===========================================================================
# KiloCodeSource
# ===========================================================================


class TestKiloCodeSource:
    def _make_task(self, tmp_path, task_id, history_data, task_meta=None):
        """Create a fake KiloCode task directory with conversation history."""
        storage = tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code" / "tasks" / task_id
        storage.mkdir(parents=True, exist_ok=True)
        history_file = storage / "api_conversation_history.json"
        history_file.write_text(json.dumps(history_data))
        if task_meta:
            meta_file = storage / "task.json"
            meta_file.write_text(json.dumps(task_meta))
        return storage

    @pytest.mark.asyncio
    async def test_poll_no_storage_dir(self, tmp_path, state, api_url):
        source = KiloCodeSource(state, api_url, storage_dir=str(tmp_path / "nonexistent"))
        pairs = await source.poll()
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_finds_pairs(self, tmp_path, state, api_url):
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "How do I create a React component?"}
            ], "ts": "2025-06-01T10:00:00Z"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "To create a React component, you can use a function..."}
            ]},
        ]
        self._make_task(tmp_path, "task-abc123", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].user_message == "How do I create a React component?"
        assert "React component" in pairs[0].assistant_message
        assert pairs[0].source_tag == "kilocode"
        assert pairs[0].timestamp == "2025-06-01T10:00:00Z"

    @pytest.mark.asyncio
    async def test_poll_detects_project_from_task_json(self, tmp_path, state, api_url):
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "What does this file do?"}
            ], "ts": "2025-01-01T00:00:00Z"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "This file implements the main logic."}
            ]},
        ]
        self._make_task(
            tmp_path, "task-proj1", history,
            task_meta={"cwd": "/home/user/MyAwesomeProject"}
        )

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].project_name == "myawesomeproject"

    @pytest.mark.asyncio
    async def test_poll_no_task_json_defaults_to_kilocode(self, tmp_path, state, api_url):
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "Question about the codebase?"}
            ], "ts": ""},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Here is the answer to your question."}
            ]},
        ]
        self._make_task(tmp_path, "task-nodef", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert pairs[0].project_name == "kilocode"

    @pytest.mark.asyncio
    async def test_poll_filters_xml_metadata(self, tmp_path, state, api_url):
        """RooCode/KiloCode injects XML metadata blocks that should be filtered."""
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "Please review my code"},
                {"type": "text", "text": "<environment_details><file>main.py</file></environment_details>"},
                {"type": "text", "text": "<task>Do something</task>"},
                {"type": "text", "text": "<feedback>Great work</feedback>"},
            ], "ts": "2025-01-01T00:00:00Z"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "I've reviewed the code and here are my suggestions."},
            ]},
        ]
        self._make_task(tmp_path, "task-xml", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 1
        # environment_details, task, and feedback should be filtered out
        assert "<environment_details>" not in pairs[0].user_message
        assert "<task>" not in pairs[0].user_message
        assert "<feedback>" not in pairs[0].user_message
        # But the real user message should remain
        assert "Please review my code" in pairs[0].user_message

    @pytest.mark.asyncio
    async def test_poll_skips_short_messages(self, tmp_path, state, api_url):
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "Hi"}
            ], "ts": ""},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Ok"}
            ]},
        ]
        self._make_task(tmp_path, "task-short", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_poll_skips_already_seen(self, tmp_path, state, api_url):
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "First question for testing?"}
            ], "ts": "2025-01-01T00:00:00Z"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "First answer for testing."}
            ]},
        ]
        self._make_task(tmp_path, "task-dedup", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))

        # First poll
        pairs1 = await source.poll()
        assert len(pairs1) == 1

        # Second poll: same mtime, should not re-process
        pairs2 = await source.poll()
        assert len(pairs2) == 0

    def test_extract_blocks_string_content(self, state, api_url):
        source = KiloCodeSource(state, api_url)
        assert source._extract_blocks("plain text") == "plain text"

    def test_extract_blocks_tool_use(self, state, api_url):
        source = KiloCodeSource(state, api_url)
        content = [
            {"type": "text", "text": "Let me search for that."},
            {"type": "tool_use", "name": "search_files"},
        ]
        result = source._extract_blocks(content)
        assert "Let me search" in result
        assert "[Tool: search_files]" in result

    def test_extract_blocks_empty(self, state, api_url):
        source = KiloCodeSource(state, api_url)
        assert source._extract_blocks([]) == ""
        assert source._extract_blocks(None) == ""

    def test_extract_blocks_filters_all_xml_tags(self, state, api_url):
        source = KiloCodeSource(state, api_url)
        content = [
            {"type": "text", "text": "<environment_details>details</environment_details>"},
            {"type": "text", "text": "<task>do stuff</task>"},
            {"type": "text", "text": "<feedback>ok</feedback>"},
            {"type": "text", "text": "<attempt_completion>done</attempt_completion>"},
            {"type": "text", "text": "<ask_followup_question>what?</ask_followup_question>"},
            {"type": "text", "text": "<new_task_created>new</new_task_created>"},
            {"type": "text", "text": "<task_completed>fin</task_completed>"},
            {"type": "text", "text": "Real message here"},
        ]
        result = source._extract_blocks(content)
        assert "Real message here" in result
        assert "<environment_details>" not in result
        assert "<task>" not in result
        assert "<feedback>" not in result
        assert "<attempt_completion>" not in result
        assert "<ask_followup_question>" not in result
        assert "<new_task_created>" not in result
        assert "<task_completed>" not in result

    @pytest.mark.asyncio
    async def test_poll_invalid_history_file(self, tmp_path, state, api_url):
        """Non-list JSON should produce no pairs (no crash)."""
        storage = tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code" / "tasks" / "bad-task"
        storage.mkdir(parents=True, exist_ok=True)
        history_file = storage / "api_conversation_history.json"
        history_file.write_text('{"not": "a list"}')

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_multiple_consecutive_assistants(self, tmp_path, state, api_url):
        """Multiple consecutive assistant messages should be joined."""
        history = [
            {"role": "user", "content": [
                {"type": "text", "text": "Explain this codebase structure"}
            ], "ts": "2025-01-01T00:00:00Z"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "The project has 3 main modules..."}
            ]},
            {"role": "assistant", "content": [
                {"type": "text", "text": "And each module handles..."}
            ]},
        ]
        self._make_task(tmp_path, "task-multi-ai", history)

        source = KiloCodeSource(state, api_url, storage_dir=str(
            tmp_path / ".vscode" / "globalStorage" / "kilocode.kilo-code"
        ))
        pairs = await source.poll()
        assert len(pairs) == 1
        assert "3 main modules" in pairs[0].assistant_message
        assert "each module handles" in pairs[0].assistant_message
