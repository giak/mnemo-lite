#!/usr/bin/env python3
"""
Backfill des embeddings manquants sur les events (EPIC-62).

Apres la migration v11→v12 (events vector(768) -> vector(1024)),
les 2 894 embeddings 768D existants ont ete perdus (DROP+RECREATE,
pattern v10→v11). Ce script regenere `embedding` pour tous les events
ou `embedding IS NULL` : a la fois les anciens (perdus par la migration)
et ceux sans embedding (DataError de creation sous la colonne 768).

Contrat d'extraction identique a EventService.create_event
(`_extract_text_for_embedding`, source_fields par defaut) :
- champs tries dans l'ordre : text > body > message > content > title
- pas de texte -> event laisse sans embedding (log, pas d'erreur)

Contrat d'ecriture (inline, asyncpg ne caste pas text -> vector) :
- UPDATE events SET embedding = '{...}'::vector WHERE id = :id

Idempotent par construction (WHERE embedding IS NULL).

Usage (dans le conteneur api) :
    docker compose exec api python scripts/backfill_event_embeddings.py [--limit N] [--dry-run]

--limit 0 = tout le corpus (defaut). --dry-run = rapporte sans ecrire.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app")

import asyncpg

from api.core import get_settings
from utils.sql_vector import format_vector_for_sql

# Champs tries par priorite, identiques a EventService.source_fields par defaut
SOURCE_FIELDS = ["text", "body", "message", "content", "title"]


def _extract_text(content: Any) -> Optional[str]:
    """Extrait le texte a vectoriser (contrat EventService, EPIC-62)."""
    if isinstance(content, dict):
        for field in SOURCE_FIELDS:
            if value := content.get(field):
                if isinstance(value, str):
                    return value
                return str(value)
    elif isinstance(content, str):
        return content
    return None


async def _count_missing(pool: asyncpg.Pool) -> int:
    """Compte les events sans embedding."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE embedding IS NULL"
        )


async def _fetch_missing(pool: asyncpg.Pool, limit: int = 0) -> List[asyncpg.Record]:
    """Recupere les events a traiter (embedding IS NULL), plus anciens d'abord."""
    query = """
        SELECT id, content
        FROM events
        WHERE embedding IS NULL
        ORDER BY timestamp ASC
    """
    if limit > 0:
        query += " LIMIT $1"
        async with pool.acquire() as conn:
            return await conn.fetch(query, limit)
    async with pool.acquire() as conn:
        return await conn.fetch(query)


async def _generate_with_retry(
    embedding_service: Any, text: str, max_retries: int = 3
) -> Optional[List[float]]:
    """Genere un embedding avec retry/backoff exponentiel (pattern EPIC-58)."""
    for attempt in range(max_retries):
        try:
            embedding = await embedding_service.generate_embedding(text)
            if embedding is None or len(embedding) == 0:
                raise ValueError("empty embedding returned")
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            return list(embedding)
        except Exception as e:
            print(f"    attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return None


async def _update_embedding(
    pool: asyncpg.Pool, event_id: Any, embedding: List[float]
) -> None:
    """Ecrit l'embedding (inline, contrat EventRepository)."""
    embedding_str = format_vector_for_sql(embedding)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE events SET embedding = $1::vector WHERE id = $2",
            embedding_str,
            event_id,
        )


async def backfill_event_embeddings(
    database_url: str,
    embedding_service: Any,
    limit: int = 0,
    dry_run: bool = False,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Backfill les embeddings manquants sur les events.

    Args:
        database_url: URL asyncpg-compatible (postgresql://).
        embedding_service: service avec `async generate_embedding(text) -> List[float]`.
        limit: 0 = tout, sinon nombre max d'events traites.
        dry_run: rapporte sans ecrire en base.
        max_retries: tentatives de generation par event (backoff 2**attempt).

    Returns:
        Dict avec total, processed, skipped_no_text, failed, updated, duration_seconds.
    """
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(database_url)
    try:
        total = await _count_missing(pool)
        if total == 0:
            print("Aucun event sans embedding, rien a faire.")
            return {
                "total": 0, "processed": 0, "skipped_no_text": 0,
                "failed": 0, "updated": 0, "duration_seconds": 0.0,
            }

        rows = await _fetch_missing(pool, limit)
        print(f"{len(rows)} events sans embedding (total: {total})")
        if dry_run:
            print("DRY-RUN : aucune ecriture en base.")
            return {
                "total": total, "processed": len(rows), "skipped_no_text": 0,
                "failed": 0, "updated": 0, "duration_seconds": 0.0,
            }

        start = datetime.utcnow()
        processed = skipped_no_text = failed = updated = 0

        for i, row in enumerate(rows, start=1):
            text = _extract_text(row["content"])
            if not text:
                skipped_no_text += 1
                continue
            processed += 1
            embedding = await _generate_with_retry(embedding_service, text, max_retries)
            if embedding is None:
                failed += 1
                print(f"    [{i}/{len(rows)}] FAILED id={row['id']}")
                continue
            await _update_embedding(pool, row["id"], embedding)
            updated += 1
            if i % 100 == 0 or i == len(rows):
                print(f"    [{i}/{len(rows)}] updated={updated} failed={failed}")

        duration = (datetime.utcnow() - start).total_seconds()
        print(
            f"Termine: processed={processed} updated={updated} "
            f"skipped_no_text={skipped_no_text} failed={failed} "
            f"durée={duration:.1f}s"
        )
        return {
            "total": total, "processed": processed, "skipped_no_text": skipped_no_text,
            "failed": failed, "updated": updated, "duration_seconds": duration,
        }
    finally:
        await pool.close()


def _build_real_embedding_service() -> Any:
    """Instancie le service d'embedding reel (meme config que le boot API)."""
    from dependencies import DualEmbeddingServiceAdapter
    from services.dual_embedding_service import DualEmbeddingService

    settings = get_settings()
    dual_service = DualEmbeddingService(
        text_model_name=settings.EMBEDDING_MODEL,
        code_model_name=settings.CODE_EMBEDDING_MODEL,
        text_dimension=settings.EMBEDDING_DIMENSION,
        code_dimension=settings.CODE_EMBEDDING_DIMENSION,
        device=settings.EMBEDDING_DEVICE,
        cache_size=settings.EMBEDDING_CACHE_SIZE,
    )
    return dual_service, DualEmbeddingServiceAdapter(dual_service)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill embeddings events (EPIC-62)")
    parser.add_argument("--limit", type=int, default=0, help="0=tout (defaut)")
    parser.add_argument("--dry-run", action="store_true", help="rapporte sans ecrire")
    args = parser.parse_args()

    database_url = get_settings().DATABASE_URL
    if not database_url:
        print("ERROR: DATABASE_URL vide, impossible de se connecter.")
        sys.exit(1)

    print("Chargement du service d'embedding (bge-m3)...")
    dual_service, embedding_service = _build_real_embedding_service()
    await dual_service.preload_models()
    print("Service pret.")
    print()

    await backfill_event_embeddings(
        database_url=database_url,
        embedding_service=embedding_service,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    asyncio.run(main())
