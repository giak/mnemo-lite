#!/usr/bin/env python3
"""
Migrate conversations from 'projects' to correct project names.
Fixes conversations that were imported with wrong project name.
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import re

# Add API path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from routes.conversations_routes import decode_project_path


async def migrate_conversations():
    """Migrate conversations from 'projects' to correct projects."""

    # Database connection
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@localhost:5432/mnemolite")
    engine = create_async_engine(database_url)

    print("=" * 70)
    print("CONVERSATION PROJECT MIGRATION")
    print("=" * 70)
    print()

    # Step 1: Get all conversations with project 'projects'
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT m.id, m.title, m.tags, p.id as project_id, p.name
            FROM memories m
            JOIN projects p ON m.project_id = p.id
            WHERE p.name = 'projects'
              AND m.memory_type = 'conversation'
        """))

        conversations = result.fetchall()

    print(f"Found {len(conversations)} conversations to migrate")
    print()

    if len(conversations) == 0:
        print("✅ No conversations to migrate!")
        return

    # Step 2: Build session -> project mapping from transcripts
    projects_dir = Path("/host/.claude/projects")
    if not projects_dir.exists():
        # Try local path if running outside container
        projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        print(f"❌ Projects directory not found: {projects_dir}")
        return

    print(f"Scanning transcripts in: {projects_dir}")

    # Find all transcript files and build session -> project mapping
    session_to_project = {}

    for transcript_file in projects_dir.glob("**/*.jsonl"):
        if transcript_file.name.startswith("agent-"):
            continue

        # Get session ID from filename
        session_id = transcript_file.stem

        # Extract project name from parent directory
        encoded_dir = transcript_file.parent.name
        real_path = decode_project_path(encoded_dir)

        if real_path:
            # Extract project name from real path
            project_name = Path(real_path).name.lower()
        else:
            # Fallback: extract from encoded directory
            project_name = encoded_dir.split('-')[-1].lower()

        # Store full session ID to project mapping
        session_to_project[session_id] = project_name

        # Also store short session ID (first 10 chars) for truncated tags
        short_session = session_id[:10]
        if short_session not in session_to_project:
            session_to_project[short_session] = project_name

    print(f"Found {len(session_to_project)} session -> project mappings")
    print()

    # Step 3: Migrate conversations
    migrated = 0
    skipped = 0
    errors = 0

    async with engine.begin() as conn:
        # Get or create project UUIDs
        project_uuids = {}

        for conv in conversations:
            try:
                # Extract session from tags (format: "session:bfc51a2f-a92")
                session_tag = None
                for tag in conv.tags:
                    if tag.startswith("session:"):
                        session_tag = tag.replace("session:", "")
                        break

                if not session_tag:
                    print(f"⚠️  Skipping {conv.title[:50]}: No session tag found")
                    skipped += 1
                    continue

                # Lookup project name for this session
                project_name = None

                # Try full session ID
                if session_tag in session_to_project:
                    project_name = session_to_project[session_tag]
                # Try short session ID (first 10 chars)
                elif session_tag[:10] in session_to_project:
                    project_name = session_to_project[session_tag[:10]]

                if not project_name:
                    print(f"⚠️  Skipping {conv.title[:50]}: Session {session_tag[:10]} not found in transcripts")
                    skipped += 1
                    continue

                # Get or create project UUID
                if project_name not in project_uuids:
                    # Try to find existing project
                    result = await conn.execute(text("""
                        SELECT id FROM projects WHERE name = :name
                    """), {"name": project_name})

                    row = result.fetchone()
                    if row:
                        project_uuids[project_name] = str(row.id)
                    else:
                        # Create new project
                        result = await conn.execute(text("""
                            INSERT INTO projects (name, description)
                            VALUES (:name, '')
                            RETURNING id
                        """), {"name": project_name})

                        project_uuids[project_name] = str(result.fetchone().id)
                        print(f"✨ Created new project: {project_name}")

                # Update conversation's project_id
                await conn.execute(text("""
                    UPDATE memories
                    SET project_id = :new_project_id
                    WHERE id = :memory_id
                """), {
                    "new_project_id": project_uuids[project_name],
                    "memory_id": str(conv.id)
                })

                migrated += 1

                if migrated % 100 == 0:
                    print(f"   Migrated {migrated}/{len(conversations)} conversations...")

            except Exception as e:
                print(f"❌ Error migrating {conv.title[:50]}: {e}")
                errors += 1

    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print()
    print(f"✅ Migrated:  {migrated}")
    print(f"⏭️  Skipped:   {skipped}")
    print(f"❌ Errors:    {errors}")
    print()

    # Step 4: Show final stats
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT p.name, COUNT(m.id) as count
            FROM projects p
            LEFT JOIN memories m ON m.project_id = p.id
            WHERE m.memory_type = 'conversation'
              AND m.author = 'AutoImport'
            GROUP BY p.name
            ORDER BY count DESC
        """))

        print("Final project distribution:")
        for row in result:
            print(f"   {row.name}: {row.count} conversations")

    print()
    print("✅ Migration complete!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_conversations())
