"""
Routes pour l'auto-import des conversations Claude Code.
EPIC-24: Auto-Save Conversations
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
import hashlib
import time
from datetime import datetime
import subprocess
import os
import uuid

from fastapi import APIRouter, HTTPException, Body, Request

from mnemo_mcp.tools.memory_tools import WriteMemoryTool
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


def get_project_name(working_dir: str = None) -> str:
    """
    Detect project name using centralized bash script.

    Falls back through multiple strategies:
    1. Execute get-project-name.sh from various locations
    2. Use basename of working directory

    Args:
        working_dir: Working directory to detect from (default: current dir)

    Returns:
        Project name in lowercase (always succeeds)

    Examples:
        >>> get_project_name("/home/user/MnemoLite")
        "mnemolite"
        >>> get_project_name()  # From /home/user/MyProject
        "myproject"
    """
    if working_dir is None:
        working_dir = os.getcwd()

    # Try to find and execute the detection script
    script_paths = [
        Path(__file__).parent.parent / "scripts" / "get-project-name.sh",
        Path(working_dir) / "scripts" / "get-project-name.sh",
    ]

    for script_path in script_paths:
        if script_path.exists():
            try:
                result = subprocess.run(
                    ["bash", str(script_path), working_dir],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().lower()
            except Exception:
                # Log silently, continue to fallback
                pass

    # Fallback: use basename of working directory
    return Path(working_dir).name.lower()


def decode_project_path(encoded_dir: str) -> str:
    """
    Decode Claude Code encoded directory name to real path.

    Examples:
        "-home-giak-Work-MnemoLite" → "/home/giak/Work/MnemoLite"
        "-home-giak-projects-truth-engine" → "/home/giak/projects/truth-engine"

    Returns:
        Real path, or empty string if not decodable
    """
    import re

    # Pattern 1: -home-USER-projects-PROJECT
    match = re.match(r'^-home-([^-]+)-projects-(.+)$', encoded_dir)
    if match:
        return f"/home/{match.group(1)}/projects/{match.group(2)}"

    # Pattern 2: -home-USER-Work-PROJECT
    match = re.match(r'^-home-([^-]+)-Work-(.+)$', encoded_dir)
    if match:
        return f"/home/{match.group(1)}/Work/{match.group(2)}"

    return ""


def parse_claude_transcripts(projects_dir: str = "/home/user/.claude/projects") -> list[tuple[str, str, str, str, str]]:
    """
    Parse Claude Code transcripts and extract user-assistant pairs.

    Returns:
        List of (user_text, assistant_text, session_id, timestamp, project_name) tuples
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

    # Find all transcript files recursively (skip agent transcripts)
    for transcript_file in transcripts_path.glob("**/*.jsonl"):
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

                        # Detect project name from transcript's parent directory
                        # transcript_file.parent.name = "-home-giak-Work-MnemoLite"
                        encoded_dir = transcript_file.parent.name

                        # Try to decode the project path (host path, may not exist in container)
                        real_path = decode_project_path(encoded_dir)

                        # Extract project name from encoded directory name
                        # Priority 1: Use get_project_name() with real path IF path exists on filesystem
                        # Priority 2: Extract directly from encoded directory name (reliable fallback)
                        if real_path and Path(real_path).exists():
                            # Path exists (e.g., running on host or path mounted in container)
                            project_name = get_project_name(real_path)
                        elif real_path:
                            # Path decoded but doesn't exist (e.g., in Docker container)
                            # Extract project name from the real path (last component)
                            project_name = Path(real_path).name.lower()
                        else:
                            # Fallback: extract from encoded directory name
                            # "-home-giak-Work-MnemoLite" → "mnemolite"
                            project_name = encoded_dir.split('-')[-1].lower()

                        conversations.append((user_text, assistant_text, session_id, timestamp, project_name))
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


@router.post("/queue")
async def queue_conversation(
    user_message: str = Body(...),
    user_message_clean: str = Body(default=""),
    assistant_message: str = Body(...),
    project_name: str = Body(...),
    session_id: str = Body(...),
    timestamp: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """
    Queue a conversation to Redis Streams for async processing by worker.

    This is the new reliable path: Hook → API → Redis → Worker → DB
    Falls back to direct save if Redis unavailable.

    Args:
        user_message: User's message content
        user_message_clean: Cleaned message for title (without system tags)
        assistant_message: Assistant's response content
        project_name: Project name (e.g. "mnemolite", "truth-engine")
        session_id: Claude Code session ID
        timestamp: Optional ISO timestamp

    Returns:
        {"success": bool, "message_id": str, "queued": bool}

    Raises:
        HTTPException: If queue fails and fallback also fails
    """
    try:
        import redis

        # Connect to Redis
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False
        )

        # Prepare timestamp
        ts = timestamp or datetime.now().isoformat()

        # Use cleaned message for title, fallback to raw if empty
        clean_msg = user_message_clean.strip() if user_message_clean else user_message[:100]

        # Push to Redis Stream
        stream_name = "conversations:autosave"
        message_id = r.xadd(
            stream_name,
            {
                b"user_message": user_message.encode('utf-8'),
                b"user_message_clean": clean_msg.encode('utf-8'),
                b"assistant_message": assistant_message.encode('utf-8'),
                b"project_name": project_name.encode('utf-8'),
                b"session_id": session_id.encode('utf-8'),
                b"timestamp": ts.encode('utf-8')
            }
        )

        logger.info(
            f"Queued conversation to Redis: {message_id.decode()} "
            f"(project={project_name}, session={session_id[:12]})"
        )

        return {
            "success": True,
            "message_id": message_id.decode(),
            "queued": True,
            "project_name": project_name
        }

    except Exception as e:
        logger.error(f"Failed to queue to Redis, falling back to direct save: {e}")

        # Fallback: Direct save (call the existing /save endpoint logic)
        # For now, just return error and let caller handle fallback
        raise HTTPException(
            status_code=503,
            detail=f"Redis queue unavailable: {str(e)}"
        )


@router.post("/save")
async def save_conversation(
    user_message: str = Body(...),
    user_message_clean: str = Body(default=""),
    assistant_message: str = Body(...),
    project_name: str = Body(...),
    session_id: str = Body(...),
    timestamp: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """
    Save a single conversation from hook (NOT auto-import).

    Called by centralized hook service with pre-extracted messages.

    Args:
        user_message: User's message content
        user_message_clean: Cleaned message for title (without system tags)
        assistant_message: Assistant's response content
        project_name: Project name (e.g. "mnemolite", "truth-engine")
        session_id: Claude Code session ID
        timestamp: Optional ISO timestamp

    Returns:
        {"success": bool, "memory_id": str}

    Raises:
        HTTPException: If save fails
    """
    try:
        # Initialize MCP tools
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

        class MockContext:
            pass
        ctx = MockContext()

        # Use cleaned message for title
        clean_msg = user_message_clean.strip() if user_message_clean else user_message[:100]

        # Create title with unique suffix to avoid duplicates
        unique_suffix = str(uuid.uuid4())[:8]
        title = f"Conv: {clean_msg[:60]}"
        if len(clean_msg) > 60:
            title += "..."
        title += f" [{unique_suffix}]"

        # Create content
        ts = timestamp or datetime.now().isoformat()
        content = f"""# Conversation - {ts}

## 👤 User
{user_message}

## 🤖 Claude
{assistant_message}

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
            "claude-code",
            f"session:{session_id[:12]}",
            f"date:{date_tag}"
        ]

        # Save via WriteMemoryTool
        result = await write_tool.execute(
            ctx=ctx,
            title=title,
            content=content,
            memory_type="conversation",
            tags=tags,
            author="AutoSave",
            project_id=project_name  # STRING name, resolves to UUID
        )

        # Cleanup
        await engine.dispose()

        logger.info(f"Saved conversation for project '{project_name}': {result.get('id')}")

        return {
            "success": True,
            "memory_id": result.get("id"),
            "project_name": project_name
        }

    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save conversation: {str(e)}")


@router.post("/import")
async def import_conversations(projects_dir: str = "/host/.claude/projects") -> Dict[str, Any]:
    """
    Import new conversations from Claude Code transcripts.

    ⚠️ DEPRECATED: One-time use only. Use auto-save queue for real-time.
    This endpoint will be removed in v2.0.

    Args:
        projects_dir: Path to .claude/projects directory (default: /host/.claude/projects)

    Returns:
        {"imported": count, "skipped": count}

    Raises:
        HTTPException: En cas d'erreur
    """
    logger.warning("DEPRECATED: /import endpoint called (use auto-save queue instead)")

    try:
        # Parse transcripts
        conversations = parse_claude_transcripts(projects_dir=projects_dir)

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
        for user_text, assistant_text, session_id, timestamp, project_name in conversations:
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
                    author="AutoImport",
                    project_id=project_name
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


@router.get("/metrics")
async def autosave_metrics(request: Request) -> Dict[str, Any]:
    """
    Get auto-save system metrics for UI dashboard.

    Returns real-time metrics from Redis queue and PostgreSQL:
    - queue_size: Number of messages in Redis stream
    - pending: Number of unacknowledged messages
    - last_save: Timestamp of most recent conversation save
    - error_count: Number of failed messages (from Redis pending errors)
    - saves_per_hour: Number of conversations saved in last hour

    Returns:
        {
            "queue_size": int,
            "pending": int,
            "last_save": str | null,
            "error_count": int,
            "saves_per_hour": int,
            "status": "healthy" | "warning" | "error"
        }
    """
    try:
        import redis
        from datetime import datetime, timedelta
        from sqlalchemy import text

        metrics = {
            "queue_size": 0,
            "pending": 0,
            "last_save": None,
            "error_count": 0,
            "saves_per_hour": 0,
            "status": "healthy"
        }

        # Get Redis metrics
        try:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))

            r = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False
            )

            stream_name = "conversations:autosave"
            group_name = "workers"

            # Get queue size (total messages in stream)
            metrics["queue_size"] = r.xlen(stream_name)

            # Get pending messages count
            try:
                pending_info = r.xpending(stream_name, group_name)
                if pending_info:
                    metrics["pending"] = pending_info.get('pending', 0)
            except:
                metrics["pending"] = 0

        except Exception as e:
            logger.warning(f"Redis metrics unavailable: {e}")
            metrics["status"] = "warning"

        # Get PostgreSQL metrics using SQLAlchemy engine from app.state
        try:
            if hasattr(request.app.state, 'db_engine') and request.app.state.db_engine:
                async with request.app.state.db_engine.connect() as conn:
                    # Get most recent conversation save
                    last_save_query = text("""
                        SELECT created_at
                        FROM memories
                        WHERE memory_type = 'conversation'
                          AND author = 'AutoSave'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """)
                    result = await conn.execute(last_save_query)
                    last_save_row = result.fetchone()

                    if last_save_row:
                        metrics["last_save"] = last_save_row[0].isoformat()

                    # Get saves per hour
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    saves_per_hour_query = text("""
                        SELECT COUNT(*)
                        FROM memories
                        WHERE memory_type = 'conversation'
                          AND author = 'AutoSave'
                          AND created_at >= :one_hour_ago
                    """)
                    result = await conn.execute(saves_per_hour_query, {"one_hour_ago": one_hour_ago})
                    saves_count_row = result.fetchone()

                    if saves_count_row:
                        metrics["saves_per_hour"] = saves_count_row[0]
            else:
                logger.warning("Database engine not available")
                metrics["status"] = "warning"

        except Exception as e:
            logger.warning(f"PostgreSQL metrics unavailable: {e}")
            metrics["status"] = "warning"

        # Determine overall status
        if metrics["pending"] > 10:
            metrics["status"] = "warning"
        if metrics["pending"] > 50:
            metrics["status"] = "error"

        return metrics

    except Exception as e:
        logger.error(f"Error fetching autosave metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch metrics: {str(e)}"
        )
