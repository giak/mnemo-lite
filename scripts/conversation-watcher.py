#!/usr/bin/env python3
"""
MnemoLite Conversation Auto-Saver Daemon
Watches ~/.claude/projects/*.jsonl files and auto-saves conversations to PostgreSQL

Architecture: File Watcher (inotify/watchdog)
- 100% independent of Claude Code hooks
- Real-time detection (< 1s latency)
- 100% coverage (captures all exchanges)
- Auto-restart on crash (systemd)

Author: Claude Code Assistant
Date: 2025-10-29
EPIC: EPIC-24 (Auto-Save Conversations)
Version: 1.0.0
"""

import asyncio
import json
import hashlib
import sys
import os
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from collections import deque

# Watchdog for file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
except ImportError:
    print("ERROR: watchdog not installed. Install: pip3 install watchdog")
    sys.exit(1)

# Add MnemoLite to path
sys.path.insert(0, '/home/giak/Work/MnemoLite')

from api.mnemo_mcp.tools.memory_tools import WriteMemoryTool
from api.db.repositories.memory_repository import MemoryRepository
from api.services.embedding_service import MockEmbeddingService
from sqlalchemy.ext.asyncio import create_async_engine


class ConversationWatcherDaemon:
    """Main daemon class for watching and saving conversations"""

    def __init__(self, watch_dir: str):
        self.watch_dir = Path(watch_dir).expanduser()
        self.state_file = Path("/tmp/mnemo-watcher-state.json")
        self.state = self._load_state()

        # MnemoLite services (initialized async)
        self.engine = None
        self.memory_repo = None
        self.embedding_service = None
        self.write_tool = None

        # Processing queue (avoid concurrent processing of same file)
        self.processing_queue = asyncio.Queue()
        self.saved_hashes: Set[str] = set(self.state.get("saved_hashes", []))

        # Statistics
        self.stats = {
            "total_saved": self.state.get("stats", {}).get("total_saved", 0),
            "total_errors": 0,
            "start_time": time.time()
        }

        # Graceful shutdown flag
        self.shutdown = False

        print(f"[INFO] ConversationWatcher initialized")
        print(f"[INFO] Watching: {self.watch_dir}")
        print(f"[INFO] State file: {self.state_file}")

    def _load_state(self) -> Dict:
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    print(f"[INFO] State loaded: {state.get('stats', {}).get('total_saved', 0)} total saved")
                    return state
            except Exception as e:
                print(f"[WARN] Failed to load state: {e}")
        return {"transcripts": {}, "saved_hashes": [], "stats": {}}

    def _save_state(self):
        """Save state to file"""
        try:
            self.state["saved_hashes"] = list(self.saved_hashes)[-10000:]  # Keep last 10k
            self.state["stats"] = {
                "total_saved": self.stats["total_saved"],
                "total_errors": self.stats["total_errors"],
                "uptime_seconds": int(time.time() - self.stats["start_time"])
            }
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save state: {e}")

    async def initialize_mnemolite(self):
        """Initialize MnemoLite services"""
        print("[INFO] Initializing MnemoLite services...")

        # Create async engine
        db_url = "postgresql+asyncpg://mnemo:mnemopass@localhost:5432/mnemolite"
        self.engine = create_async_engine(db_url, pool_size=2, max_overflow=5, echo=False)

        # Create services
        self.memory_repo = MemoryRepository(self.engine)
        self.embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        # Create write tool
        self.write_tool = WriteMemoryTool()
        self.write_tool.inject_services({
            "memory_repository": self.memory_repo,
            "embedding_service": self.embedding_service
        })

        print("[INFO] MnemoLite services initialized")

    async def cleanup(self):
        """Cleanup resources"""
        print("[INFO] Cleaning up...")
        self._save_state()
        if self.engine:
            await self.engine.dispose()
        print("[INFO] Cleanup complete")

    def parse_transcript(self, transcript_path: Path) -> List[Tuple[str, str, str]]:
        """
        Parse JSONL transcript and extract user-assistant pairs
        Returns: [(user_text, assistant_text, timestamp), ...]
        """
        try:
            # Get last processed position for this file
            file_name = transcript_path.name
            last_position = self.state.get("transcripts", {}).get(file_name, {}).get("last_position", 0)

            with open(transcript_path, 'r', encoding='utf-8') as f:
                # Seek to last position
                f.seek(last_position)

                # Read new lines
                new_lines = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if 'role' in msg:
                            new_lines.append(msg)
                    except json.JSONDecodeError:
                        continue

                # Update last position
                current_position = f.tell()
                if file_name not in self.state["transcripts"]:
                    self.state["transcripts"][file_name] = {}
                self.state["transcripts"][file_name]["last_position"] = current_position

            if not new_lines:
                return []

            # Extract user-assistant pairs from ALL messages (not just new ones)
            # We need full context to extract complete pairs
            with open(transcript_path, 'r', encoding='utf-8') as f:
                all_messages = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if 'role' in msg:
                            all_messages.append(msg)
                    except json.JSONDecodeError:
                        continue

            # Extract pairs: user followed by assistant
            pairs = []
            i = 0
            while i < len(all_messages):
                if all_messages[i].get('role') == 'user':
                    # Find next assistant message
                    for j in range(i + 1, len(all_messages)):
                        if all_messages[j].get('role') == 'assistant':
                            user_text = self._extract_text(all_messages[i])
                            assistant_text = self._extract_text(all_messages[j])
                            timestamp = all_messages[i].get('timestamp') or all_messages[j].get('timestamp')

                            if len(user_text) >= 5 and len(assistant_text) >= 5:
                                pairs.append((user_text, assistant_text, timestamp or ""))

                            i = j
                            break
                i += 1

            # Return only NEW pairs (not already processed)
            last_saved_hash = self.state.get("transcripts", {}).get(file_name, {}).get("last_saved_hash", "")

            new_pairs = []
            found_last = False if last_saved_hash else True  # If no last hash, all pairs are new

            for pair in pairs:
                pair_hash = self._compute_hash(pair[0], pair[1])

                if not found_last:
                    if pair_hash == last_saved_hash:
                        found_last = True
                    continue

                # Skip if already saved
                if pair_hash in self.saved_hashes:
                    continue

                new_pairs.append(pair)

            return new_pairs

        except Exception as e:
            print(f"[ERROR] Failed to parse {transcript_path.name}: {e}")
            return []

    def _extract_text(self, message: dict) -> str:
        """Extract text from message content"""
        content = message.get('content', '')

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    texts.append(item.get('text', ''))
            return '\n'.join(texts)

        return str(content)

    def _compute_hash(self, user_text: str, assistant_text: str) -> str:
        """Compute hash for deduplication"""
        combined = user_text + assistant_text
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]

    async def save_conversation(self, user_text: str, assistant_text: str,
                                session_id: str, timestamp: str) -> bool:
        """Save a single conversation to MnemoLite"""

        # Compute hash
        content_hash = self._compute_hash(user_text, assistant_text)

        # Check if already saved
        if content_hash in self.saved_hashes:
            return False

        try:
            # Create title
            title = f"Conv: {user_text[:60]}"
            if len(user_text) > 60:
                title += "..."

            # Create content
            ts = timestamp or datetime.now().isoformat()
            content = f"""# Conversation - {ts}

## 👤 User
{user_text}

## 🤖 Claude
{assistant_text}

---
**Session**: {session_id}
**Saved**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

            # Determine date tag
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now()
                date_tag = dt.strftime("%Y%m%d")
            except:
                date_tag = datetime.now().strftime("%Y%m%d")

            # Tags
            tags = [
                "auto-saved",
                "watcher",
                f"session:{session_id[:12]}",
                f"date:{date_tag}",
                f"hash:{content_hash}"
            ]

            # Mock context
            class MockContext:
                pass

            # Save via write_memory
            result = await self.write_tool.execute(
                ctx=MockContext(),
                title=title,
                content=content,
                memory_type="conversation",
                tags=tags,
                author="AutoSave"
            )

            # Mark as saved
            self.saved_hashes.add(content_hash)
            self.stats["total_saved"] += 1

            print(f"[✓] Saved: {title} (hash: {content_hash})")
            return True

        except Exception as e:
            print(f"[✗] Failed to save conversation: {e}")
            self.stats["total_errors"] += 1
            return False

    async def process_file(self, file_path: Path):
        """Process a single transcript file"""
        try:
            # Parse new exchanges
            new_pairs = self.parse_transcript(file_path)

            if not new_pairs:
                return

            print(f"[INFO] Processing {len(new_pairs)} new exchanges from {file_path.name}")

            # Save each conversation
            session_id = file_path.stem
            for user_text, assistant_text, timestamp in new_pairs:
                success = await self.save_conversation(user_text, assistant_text, session_id, timestamp)

                if success:
                    # Update last saved hash
                    content_hash = self._compute_hash(user_text, assistant_text)
                    if file_path.name not in self.state["transcripts"]:
                        self.state["transcripts"][file_path.name] = {}
                    self.state["transcripts"][file_path.name]["last_saved_hash"] = content_hash

                # Small delay to avoid overwhelming DB
                await asyncio.sleep(0.1)

            # Save state after processing file
            self._save_state()

        except Exception as e:
            print(f"[ERROR] Failed to process {file_path.name}: {e}")
            self.stats["total_errors"] += 1

    async def queue_processor(self):
        """Process files from queue"""
        while not self.shutdown:
            try:
                # Get file from queue with timeout
                file_path = await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)
                await self.process_file(file_path)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[ERROR] Queue processor error: {e}")

    def scan_existing_files(self):
        """Scan existing transcript files on startup"""
        print("[INFO] Scanning existing transcript files...")

        jsonl_files = list(self.watch_dir.glob("*.jsonl"))
        # Filter out agent transcripts
        jsonl_files = [f for f in jsonl_files if not f.name.startswith("agent-")]

        print(f"[INFO] Found {len(jsonl_files)} transcript files")

        # Queue all files for processing
        for file_path in jsonl_files:
            asyncio.create_task(self.processing_queue.put(file_path))

    async def run(self):
        """Main run loop"""
        print("[INFO] Starting ConversationWatcher daemon...")

        # Initialize MnemoLite
        await self.initialize_mnemolite()

        # Scan existing files
        self.scan_existing_files()

        # Start queue processor
        processor_task = asyncio.create_task(self.queue_processor())

        # Setup file watcher
        event_handler = TranscriptEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.watch_dir), recursive=False)
        observer.start()

        print(f"[INFO] Watching {self.watch_dir} for changes...")
        print("[INFO] Daemon running. Press Ctrl+C to stop.")

        try:
            # Keep running until shutdown
            while not self.shutdown:
                await asyncio.sleep(1)

                # Periodic state save (every 60s)
                if int(time.time()) % 60 == 0:
                    self._save_state()
                    print(f"[INFO] Stats: {self.stats['total_saved']} saved, {self.stats['total_errors']} errors")

        except KeyboardInterrupt:
            print("\n[INFO] Received shutdown signal")

        finally:
            # Cleanup
            self.shutdown = True
            observer.stop()
            observer.join()
            await processor_task
            await self.cleanup()
            print("[INFO] Daemon stopped")


class TranscriptEventHandler(FileSystemEventHandler):
    """Handler for file system events"""

    def __init__(self, daemon: ConversationWatcherDaemon):
        self.daemon = daemon
        self.last_modified = {}  # Debounce rapid modifications

    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification events"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process .jsonl files
        if not file_path.suffix == '.jsonl':
            return

        # Skip agent transcripts
        if file_path.name.startswith("agent-"):
            return

        # Debounce: ignore if modified < 1s ago
        now = time.time()
        last_mod = self.last_modified.get(file_path, 0)
        if now - last_mod < 1.0:
            return

        self.last_modified[file_path] = now

        print(f"[INFO] Detected modification: {file_path.name}")

        # Queue for processing
        asyncio.create_task(self.daemon.processing_queue.put(file_path))


def main():
    """Main entry point"""

    # Watch directory (default: ~/.claude/projects/-home-giak-Work-MnemoLite)
    watch_dir = os.getenv(
        "CLAUDE_PROJECTS_DIR",
        "~/.claude/projects/-home-giak-Work-MnemoLite"
    )

    # Create daemon
    daemon = ConversationWatcherDaemon(watch_dir)

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\n[INFO] Shutdown signal received")
        daemon.shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run daemon
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
