#!/usr/bin/env python3
"""
Import Claude Code conversations into MnemoLite
Parse ~/.claude/projects/*.jsonl and save to PostgreSQL with embeddings

Usage:
    python3 scripts/import-conversations.py                    # Import all new
    python3 scripts/import-conversations.py --all              # Re-import all
    python3 scripts/import-conversations.py --since 2025-10-29 # Import since date

No external dependencies - uses MnemoLite MCP tools directly.

Author: Claude Code Assistant
Date: 2025-10-29
EPIC: EPIC-24 (Auto-save Conversations)
"""

import asyncio
import json
import glob
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional

# Add MnemoLite to path
sys.path.insert(0, '/app')

from mnemo_mcp.tools.memory_tools import WriteMemoryTool
from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService
from sqlalchemy.ext.asyncio import create_async_engine


class ConversationImporter:
    """Simple conversation importer using MnemoLite MCP tools"""

    def __init__(self):
        self.engine = None
        self.memory_repo = None
        self.embedding_service = None
        self.write_tool = None

    async def initialize(self):
        """Initialize MnemoLite services"""
        print("🔧 Initializing MnemoLite services...")

        # Create async engine
        db_url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
        self.engine = create_async_engine(db_url, pool_size=5)

        # Create services
        self.memory_repo = MemoryRepository(self.engine)
        self.embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        # Create write tool
        self.write_tool = WriteMemoryTool()
        self.write_tool.inject_services({
            "memory_repository": self.memory_repo,
            "embedding_service": self.embedding_service
        })

        print("✅ Services initialized")

    async def cleanup(self):
        """Cleanup resources"""
        if self.engine:
            await self.engine.dispose()

    def find_transcripts(self, project_dir: str = None) -> List[Path]:
        """Find all Claude Code transcript files"""
        if project_dir is None:
            # In Docker container, mounted at /home/user/.claude/projects
            project_dir = "/home/user/.claude/projects/-home-giak-Work-MnemoLite"

        transcripts = list(Path(project_dir).glob("*.jsonl"))
        # Filter out agent transcripts
        transcripts = [t for t in transcripts if not t.name.startswith("agent-")]

        print(f"📁 Found {len(transcripts)} transcript files")
        return transcripts

    def parse_transcript(self, transcript_path: Path) -> List[Tuple[dict, dict]]:
        """Parse JSONL transcript and extract user-assistant pairs"""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                messages = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if 'role' in msg:
                            messages.append(msg)
                    except json.JSONDecodeError:
                        continue

            # Extract pairs: user message followed by assistant response
            pairs = []
            i = 0
            while i < len(messages):
                if messages[i].get('role') == 'user':
                    # Find next assistant message
                    for j in range(i + 1, len(messages)):
                        if messages[j].get('role') == 'assistant':
                            pairs.append((messages[i], messages[j]))
                            i = j
                            break
                i += 1

            return pairs

        except Exception as e:
            print(f"⚠️  Error parsing {transcript_path.name}: {e}")
            return []

    def extract_text(self, message: dict) -> str:
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

    def compute_hash(self, user_text: str, assistant_text: str) -> str:
        """Compute hash for deduplication"""
        combined = user_text + assistant_text
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]

    async def already_imported(self, content_hash: str) -> bool:
        """Check if conversation already imported"""
        try:
            # Check if memory with this hash tag exists
            memories, total = await self.memory_repo.list_memories(
                filters=MemoryFilters(tags=[f"hash:{content_hash}"]),
                limit=1,
                offset=0
            )
            return total > 0
        except Exception:
            return False

    async def import_conversation(
        self,
        user_text: str,
        assistant_text: str,
        session_id: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """Import a single conversation into MnemoLite"""

        # Compute hash for deduplication
        content_hash = self.compute_hash(user_text, assistant_text)

        # Check if already imported
        if await self.already_imported(content_hash):
            return False  # Skip, already exists

        # Create title from first 50 chars of user message
        title = f"Conv: {user_text[:50]}"
        if len(user_text) > 50:
            title += "..."

        # Create full content
        content = f"User: {user_text}\n\nClaude: {assistant_text}"

        # Determine date tag
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_tag = dt.strftime("%Y%m%d")
            except:
                date_tag = datetime.now().strftime("%Y%m%d")
        else:
            date_tag = datetime.now().strftime("%Y%m%d")

        # Tags
        tags = [
            "imported",
            "claude-code",
            f"session:{session_id[:12]}",
            f"date:{date_tag}",
            f"hash:{content_hash}"
        ]

        # Mock context (WriteMemoryTool expects a context object)
        class MockContext:
            pass

        try:
            # Call write_memory tool
            result = await self.write_tool.execute(
                ctx=MockContext(),
                title=title,
                content=content,
                memory_type="conversation",
                tags=tags,
                author="BatchImport"
            )

            return True  # Successfully imported

        except Exception as e:
            print(f"   ⚠️  Failed to import: {e}")
            return False

    async def import_all(
        self,
        since_date: Optional[datetime] = None,
        force_reimport: bool = False
    ):
        """Import all conversations from transcripts"""

        print("=" * 70)
        print("📚 CLAUDE CODE CONVERSATIONS IMPORT")
        print("=" * 70)
        print()

        # Find transcripts
        transcripts = self.find_transcripts()

        if not transcripts:
            print("❌ No transcript files found")
            return

        total_conversations = 0
        imported_count = 0
        skipped_count = 0
        failed_count = 0

        for transcript in transcripts:
            session_id = transcript.stem
            print(f"\n📄 Processing: {transcript.name}")

            # Parse transcript
            pairs = self.parse_transcript(transcript)
            print(f"   Found {len(pairs)} conversations")

            if not pairs:
                continue

            total_conversations += len(pairs)

            # Import each conversation
            for user_msg, assistant_msg in pairs:
                user_text = self.extract_text(user_msg)
                assistant_text = self.extract_text(assistant_msg)

                # Skip if too short
                if len(user_text) < 5 or len(assistant_text) < 5:
                    continue

                # Get timestamp
                timestamp = user_msg.get('timestamp') or assistant_msg.get('timestamp')

                # Check date filter
                if since_date and timestamp:
                    try:
                        msg_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        if msg_date < since_date:
                            skipped_count += 1
                            continue
                    except:
                        pass

                # Import
                success = await self.import_conversation(
                    user_text,
                    assistant_text,
                    session_id,
                    timestamp
                )

                if success:
                    imported_count += 1
                    print("   ✓", end="", flush=True)
                else:
                    skipped_count += 1
                    print("   ·", end="", flush=True)

            print()  # Newline after dots

        # Summary
        print()
        print("=" * 70)
        print("📊 IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total conversations found: {total_conversations}")
        print(f"✅ Imported: {imported_count}")
        print(f"⊘  Skipped (duplicates): {skipped_count}")
        print(f"❌ Failed: {failed_count}")
        print()

        if imported_count > 0:
            print(f"🎉 Successfully imported {imported_count} conversations to MnemoLite!")
        else:
            print("ℹ️  No new conversations to import")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Import Claude Code conversations to MnemoLite")
    parser.add_argument('--all', action='store_true', help='Re-import all conversations')
    parser.add_argument('--since', type=str, help='Import only since date (YYYY-MM-DD)')
    parser.add_argument('--project-dir', type=str, help='Custom Claude Code project directory')

    args = parser.parse_args()

    # Parse since date
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, '%Y-%m-%d')
            print(f"📅 Importing conversations since {since_date.strftime('%Y-%m-%d')}")
        except ValueError:
            print(f"❌ Invalid date format: {args.since}. Use YYYY-MM-DD")
            return

    # Create importer
    importer = ConversationImporter()

    try:
        # Initialize
        await importer.initialize()

        # Import conversations
        await importer.import_all(
            since_date=since_date,
            force_reimport=args.all
        )

    finally:
        # Cleanup
        await importer.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
