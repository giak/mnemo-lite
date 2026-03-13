#!/usr/bin/env python3
"""
Bulk import Truth Engine investigations into MnemoLite.

Usage:
    docker compose exec -T api python3 scripts/bulk_import_investigations.py /path/to/logs/
"""

import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add api directory to path for imports
sys.path.insert(0, '/app')

import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from db.repositories.memory_repository import MemoryRepository
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from mnemo_mcp.models.memory_models import MemoryType, MemoryCreate

logger = structlog.get_logger()


def extract_metadata(filepath: Path) -> dict:
    """Extract metadata from investigation file."""
    filename = filepath.stem
    
    # Extract date from filename (YYYY-MM-DD)
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', filename)
    date_str = date_match.group(1) if date_match else None
    
    # Extract subject (after date and optional timestamp)
    subject = re.sub(r'^\d{4}-\d{2}-\d{2}_(\d{2}-\d{2}-\d{2}_)?', '', filename)
    
    # Read first lines for title
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        content = first_line + '\n' + f.read()
    
    # Extract title from first # heading
    title_match = re.match(r'^#\s*(.+)$', first_line)
    title = title_match.group(1) if title_match else f"Investigation: {subject}"
    
    # Truncate title if too long
    if len(title) > 195:
        title = title[:192] + "..."
    
    # Generate tags from subject
    tags = [t for t in re.split(r'[-_]', subject) if t and len(t) > 1][:8]
    tags = ['truth-engine', 'investigation'] + tags
    
    return {
        'title': title,
        'content': content,
        'tags': tags,
        'date': date_str,
        'subject': subject,
        'filepath': str(filepath),
    }


async def import_investigation(
    repo: MemoryRepository,
    embedding_service,
    metadata: dict,
    dry_run: bool = False,
) -> Optional[str]:
    """Import a single investigation file."""
    
    if dry_run:
        print(f"  [DRY-RUN] Would import: {metadata['title'][:60]}...")
        return None
    
    # Generate embedding from title + first 2000 chars of content
    embedding_text = f"{metadata['title']}\n\n{metadata['content'][:2000]}"
    
    embedding = None
    try:
        # DualEmbeddingService returns {'text': [...]} dict
        result = await embedding_service.generate_embedding(embedding_text, domain=EmbeddingDomain.TEXT)
        embedding = result.get('text')  # Extract the actual vector
    except Exception as e:
        logger.warning(f"Embedding failed for {metadata['subject']}: {e}")
    
    # Create memory object
    memory_create = MemoryCreate(
        title=metadata['title'],
        content=metadata['content'],
        memory_type=MemoryType.INVESTIGATION,
        tags=metadata['tags'],
        author="Truth Engine",
        project_id=None,  # Global memory
        related_chunks=[],
        resource_links=[{"uri": f"file://{metadata['filepath']}", "type": "source"}],
        embedding_source=None,
    )
    
    # Save to database
    memory = await repo.create(memory_create, embedding)
    
    return str(memory.id)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/bulk_import_investigations.py <logs_directory> [--dry-run]")
        sys.exit(1)
    
    logs_dir = Path(sys.argv[1])
    dry_run = '--dry-run' in sys.argv
    
    if not logs_dir.exists():
        print(f"Error: Directory not found: {logs_dir}")
        sys.exit(1)
    
    # Get all .md files
    md_files = sorted(logs_dir.glob("*.md"))
    print(f"Found {len(md_files)} investigation files in {logs_dir}")
    
    if dry_run:
        print("[DRY-RUN MODE] No changes will be made")
    
    # Connect to database
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@postgres:5432/mnemolite")
    engine = create_async_engine(database_url)
    
    # Create embedding service
    embedding_service = DualEmbeddingService(
        text_model_name=os.environ.get("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
        code_model_name=os.environ.get("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code"),
        dimension=int(os.environ.get("EMBEDDING_DIMENSION", "768")),
        device=os.environ.get("EMBEDDING_DEVICE", "cpu"),
        cache_size=1000
    )
    
    async with engine.begin() as conn:
        repo = MemoryRepository(engine)
        
        imported = 0
        skipped = 0
        errors = 0
        
        for i, filepath in enumerate(md_files, 1):
            try:
                metadata = extract_metadata(filepath)
                
                # Skip very small files (likely empty or just headers)
                if len(metadata['content']) < 500:
                    print(f"  [{i}/{len(md_files)}] SKIP (too small): {filepath.name}")
                    skipped += 1
                    continue
                
                memory_id = await import_investigation(
                    repo, embedding_service, metadata, dry_run=dry_run
                )
                
                if dry_run:
                    imported += 1
                elif memory_id:
                    print(f"  [{i}/{len(md_files)}] OK: {metadata['subject'][:50]} -> {memory_id[:8]}...")
                    imported += 1
                
            except Exception as e:
                print(f"  [{i}/{len(md_files)}] ERROR: {filepath.name}: {e}")
                errors += 1
                continue
            
            # Progress update every 20 files
            if i % 20 == 0:
                print(f"--- Progress: {i}/{len(md_files)} ({imported} imported, {errors} errors) ---")
        
        print(f"\n=== COMPLETE ===")
        print(f"Total files: {len(md_files)}")
        print(f"Imported: {imported}")
        print(f"Skipped: {skipped}")
        print(f"Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
