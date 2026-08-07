#!/usr/bin/env python3
"""
Backfill des embeddings manquants sur les memories (EPIC-58).

Régénère `embedding_half` (et `embedding`) pour toutes les mémoires où
`embedding_half IS NULL` : l'embedding async du write (EPIC-53) échoue
(timeout, service down) et n'est jamais retenté. Ces mémoires sont
invisibles de toute recherche vectorielle et du RRF hybride.

Contrat identique à l'écriture async EPIC-53 (`_trigger_async_embedding`) :
- texte vectorisé : `title. {embedding_source or content}` (si titre),
  sinon `embedding_source or content`
- écriture : `embedding` (::vector), `embedding_half` (::halfvec),
  `embedding_model` (settings.EMBEDDING_MODEL)
- service : DualEmbeddingServiceAdapter (même instance que le boot API)
- retry : backoff exponentiel (pattern `_generate_embedding_with_retry`)

Idempotent par construction (WHERE embedding_half IS NULL) : relancer ne
régénère pas l'existant.

Usage (dans le conteneur api) :
    docker compose exec api python scripts/backfill_memory_embeddings.py [--limit N] [--dry-run]

--limit 0 = tout le corpus (défaut). --dry-run = rapporte sans écrire.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app")

import asyncpg

from api.core import get_settings
from utils.sql_vector import format_vector_for_sql


async def _count_missing(pool: asyncpg.Pool) -> int:
    """Compte les mémoires sans embedding_half."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM memories
            WHERE embedding_half IS NULL
              AND deleted_at IS NULL
            """
        )


async def _fetch_missing(pool: asyncpg.Pool, limit: int = 0) -> List[asyncpg.Record]:
    """Récupère les mémoires à traiter (embedding_half IS NULL)."""
    query = """
        SELECT id, title, content, embedding_source
        FROM memories
        WHERE embedding_half IS NULL
          AND deleted_at IS NULL
        ORDER BY created_at DESC
    """
    if limit > 0:
        query += " LIMIT $1"
        async with pool.acquire() as conn:
            return await conn.fetch(query, limit)
    async with pool.acquire() as conn:
        return await conn.fetch(query)


def _build_embedding_text(title: Optional[str], content: str, embedding_source: Optional[str]) -> str:
    """Construit le texte à vectoriser (contrat EPIC-53 identique au write)."""
    if title:
        return f"{title}. {embedding_source or content}"
    return embedding_source or content


async def _generate_with_retry(
    embedding_service: Any, text: str, max_retries: int = 3
) -> Optional[List[float]]:
    """Génère un embedding avec retry/backoff exponentiel (2**attempt s)."""
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
    pool: asyncpg.Pool, memory_id: Any, embedding: List[float], model: str
) -> None:
    """Écrit embedding + embedding_half + embedding_model (contrat EPIC-53)."""
    embedding_str = format_vector_for_sql(embedding)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE memories
            SET embedding = $1::vector,
                embedding_half = $2::halfvec,
                embedding_model = $3,
                updated_at = NOW()
            WHERE id = $4
            """,
            embedding_str,
            embedding_str,
            model,
            memory_id,
        )


async def backfill_memory_embeddings(
    database_url: str,
    embedding_service: Any,
    limit: int = 0,
    dry_run: bool = False,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Backfill les embeddings manquants.

    Args:
        database_url: URL asyncpg-compatible (postgresql://).
        embedding_service: service avec `async generate_embedding(text) -> List[float]`.
        limit: 0 = tout, sinon nombre max de mémoires traitées.
        dry_run: rapporte sans écrire en base.
        max_retries: tentatives de génération par mémoire (backoff 2**attempt).

    Returns:
        Dict avec total, processed, failed, duration_seconds.
    """
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3, command_timeout=120)
    try:
        total_missing = await _count_missing(pool)
        rows = await _fetch_missing(pool, limit)
        settings = get_settings()
        model = settings.EMBEDDING_MODEL

        print(f"Total sans embedding_half : {total_missing:,}")
        print(f"Traitement de {len(rows)} mémoire(s) (limit={limit or 'all'}, dry_run={dry_run})")
        print()

        processed = 0
        failed = 0
        start = datetime.now()

        for i, row in enumerate(rows, 1):
            memory_id = row["id"]
            text = _build_embedding_text(row["title"], row["content"] or "", row["embedding_source"])
            print(f"  [{i}/{len(rows)}] {str(memory_id)[:8]}... ", end="")

            embedding = await _generate_with_retry(embedding_service, text, max_retries)
            if embedding is None:
                failed += 1
                print(f"ERROR (after {max_retries} attempts)")
                continue

            if not dry_run:
                await _update_embedding(pool, memory_id, embedding, model)
            processed += 1
            print(f"OK (dim={len(embedding)})")

        duration = (datetime.now() - start).total_seconds()

        print()
        print("=" * 60)
        print(f"RESULT : {processed} traités, {failed} en échec, {total_missing} manquants au départ")
        print(f"TIME   : {duration:.2f}s")
        if processed > 0 and duration > 0:
            rate = processed / duration
            print(f"RATE   : {rate:.2f} mémoires/s")
            if not dry_run:
                remaining = await _count_missing(pool)
                print(f"RESTE  : {remaining:,} sans embedding_half")
        print("=" * 60)

        return {
            "total": total_missing,
            "processed": processed,
            "failed": failed,
            "duration_seconds": duration,
        }
    finally:
        await pool.close()


def _build_real_embedding_service() -> Any:
    """Instancie le service d'embedding réel (même config que le boot API, main.py)."""
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
    parser = argparse.ArgumentParser(description="Backfill des embeddings manquants (EPIC-58)")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max de mémoires (0 = tout)")
    parser.add_argument("--dry-run", action="store_true", help="Rapporte sans écrire en base")
    args = parser.parse_args()

    database_url = get_settings().DATABASE_URL
    if not database_url:
        print("ERROR: DATABASE_URL vide, impossible de se connecter.")
        sys.exit(1)

    print("Chargement du service d'embedding (bge-m3)...")
    dual_service, embedding_service = _build_real_embedding_service()
    await dual_service.preload_models()
    print("Service prêt.")
    print()

    await backfill_memory_embeddings(
        database_url=database_url,
        embedding_service=embedding_service,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    asyncio.run(main())
