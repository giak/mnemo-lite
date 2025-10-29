"""
Routes pour l'auto-import des conversations Claude Code.
EPIC-24: Auto-Save Conversations
"""

import logging
from typing import Dict, Any
from pathlib import Path
import json
import hashlib
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from mnemo_mcp.tools.memory_tools import WriteMemoryTool
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


def parse_claude_transcripts(projects_dir: str = "/home/user/.claude/projects") -> list[tuple[str, str, str, str]]:
    """
    Parse Claude Code transcripts and extract user-assistant pairs.

    Returns:
        List of (user_text, assistant_text, session_id, timestamp) tuples
    """
    transcripts_path = Path(projects_dir)

    if not transcripts_path.exists():
        logger.warning(f"Projects directory not found: {projects_dir}")
        return []

    conversations = []
    state_file = Path("/tmp/mnemo-conversations-state.json")

    # Load saved hashes (deduplication)
    saved_hashes = set()
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            saved_hashes = set(state.get("saved_hashes", []))
        except:
            pass

    # Find all transcript files (skip agent transcripts)
    for transcript_file in transcripts_path.glob("*.jsonl"):
        if transcript_file.name.startswith("agent-"):
            continue

        try:
            # Cooldown: Skip files modified less than 120 seconds ago
            # This prevents importing incomplete messages while Claude is still writing
            # 120s = 2 minutes to handle long responses
            file_age = time.time() - transcript_file.stat().st_mtime
            if file_age < 120:
                logger.debug(f"Skipping {transcript_file.name} (modified {file_age:.0f}s ago, waiting for cooldown)")
                continue

            # Parse JSONL
            messages = []
            with open(transcript_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        # Claude Code format: {"message": {"role": "...", "content": ...}}
                        if 'message' in msg and 'role' in msg['message']:
                            messages.append(msg['message'])
                    except json.JSONDecodeError:
                        continue

            # Extract EACH user-assistant pair as a SEPARATE conversation
            i = 0
            while i < len(messages):
                if messages[i].get('role') == 'user':
                    user_content = messages[i].get('content', '')

                    # FILTER: Skip tool_result messages (they're not real user messages)
                    is_tool_result = False
                    if isinstance(user_content, list):
                        is_tool_result = any(
                            isinstance(item, dict) and item.get('type') == 'tool_result'
                            for item in user_content
                        )

                    if is_tool_result:
                        i += 1
                        continue

                    # Extract text from REAL user message
                    if isinstance(user_content, list):
                        user_text = '\n'.join([
                            item.get('text', '')
                            for item in user_content
                            if isinstance(item, dict) and item.get('type') == 'text'
                        ])
                    elif isinstance(user_content, str):
                        user_text = user_content
                    else:
                        user_text = str(user_content)

                    # Skip if no user text
                    if len(user_text) < 5:
                        i += 1
                        continue

                    # Collect ALL consecutive assistant messages until next REAL user
                    assistant_contents = []
                    j = i + 1

                    while j < len(messages):
                        if messages[j].get('role') == 'user':
                            # Check if it's a real user message or tool_result
                            next_user_content = messages[j].get('content', '')
                            is_next_tool_result = False

                            if isinstance(next_user_content, list):
                                is_next_tool_result = any(
                                    isinstance(item, dict) and item.get('type') == 'tool_result'
                                    for item in next_user_content
                                )

                            if not is_next_tool_result:
                                # Real user message - stop collecting assistant messages
                                break
                            else:
                                # Tool result - skip it and continue
                                j += 1
                                continue

                        elif messages[j].get('role') == 'assistant':
                            assistant_contents.append(messages[j].get('content', ''))

                        j += 1

                    # If we found at least one assistant message
                    if assistant_contents:

                        # Process ALL assistant contents and concatenate
                        assistant_text_parts = []
                        for assistant_content in assistant_contents:
                            if isinstance(assistant_content, list):
                                # Extract 'text' and 'thinking' content
                                for item in assistant_content:
                                    if not isinstance(item, dict):
                                        continue
                                    if item.get('type') == 'text':
                                        assistant_text_parts.append(item.get('text', ''))
                                    elif item.get('type') == 'thinking':
                                        # Include thinking content (Claude's internal reasoning)
                                        thinking = item.get('thinking', '')
                                        if thinking:
                                            assistant_text_parts.append(f"[Thinking: {thinking[:200]}...]")
                            elif isinstance(assistant_content, str):
                                assistant_text_parts.append(assistant_content)
                            else:
                                assistant_text_parts.append(str(assistant_content))

                        assistant_text = '\n'.join(assistant_text_parts)

                        # Skip if too short
                        if len(user_text) < 5 or len(assistant_text) < 5:
                            i = j
                            continue

                        # Deduplication check - EACH exchange gets its own hash
                        content_hash = hashlib.sha256(
                            (user_text + assistant_text).encode()
                        ).hexdigest()[:16]

                        if content_hash in saved_hashes:
                            i = j
                            continue

                        # Add as SEPARATE conversation
                        session_id = transcript_file.stem
                        timestamp = messages[i].get('timestamp') or ""

                        conversations.append((user_text, assistant_text, session_id, timestamp))
                        saved_hashes.add(content_hash)

                        i = j
                    else:
                        i += 1
                else:
                    i += 1

        except Exception as e:
            logger.error(f"Error parsing {transcript_file.name}: {e}")
            continue

    # Save state
    try:
        state_file.write_text(json.dumps({
            "saved_hashes": list(saved_hashes)[-10000:],
            "last_import": datetime.now().isoformat()
        }))
    except:
        pass

    return conversations


@router.post("/import")
async def import_conversations() -> Dict[str, Any]:
    """
    Import new conversations from Claude Code transcripts.

    Scans ~/.claude/projects/*.jsonl files, extracts user-assistant pairs,
    and saves them to MnemoLite memories table with embeddings.

    Returns:
        {"imported": count, "skipped": count}

    Raises:
        HTTPException: En cas d'erreur
    """
    try:
        # Parse transcripts
        conversations = parse_claude_transcripts()

        if not conversations:
            return {"imported": 0, "skipped": 0, "message": "No new conversations found"}

        logger.info(f"Found {len(conversations)} conversations to import")

        # Initialize MCP tools (same as MCP server does)
        from sqlalchemy.ext.asyncio import create_async_engine

        db_url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
        engine = create_async_engine(db_url, pool_size=2)

        memory_repo = MemoryRepository(engine)
        embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        write_tool = WriteMemoryTool()
        write_tool.inject_services({
            "memory_repository": memory_repo,
            "embedding_service": embedding_service
        })

        # Mock context (WriteMemoryTool expects this)
        class MockContext:
            pass

        ctx = MockContext()

        # Save each conversation
        imported = 0
        for user_text, assistant_text, session_id, timestamp in conversations:
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
**Imported**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

                # Determine date tag
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now()
                    date_tag = dt.strftime("%Y%m%d")
                except:
                    date_tag = datetime.now().strftime("%Y%m%d")

                # Tags
                tags = [
                    "auto-imported",
                    "claude-code",
                    f"session:{session_id[:12]}",
                    f"date:{date_tag}"
                ]

                # Save via WriteMemoryTool (generates embeddings)
                await write_tool.execute(
                    ctx=ctx,
                    title=title,
                    content=content,
                    memory_type="conversation",
                    tags=tags,
                    author="AutoImport"
                )

                imported += 1

            except Exception as e:
                logger.error(f"Failed to import conversation: {e}")
                continue

        # Cleanup
        await engine.dispose()

        logger.info(f"Successfully imported {imported}/{len(conversations)} conversations")

        return {
            "imported": imported,
            "skipped": len(conversations) - imported,
            "message": f"Imported {imported} conversations"
        }

    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Import failed: {str(e)}"
        )
