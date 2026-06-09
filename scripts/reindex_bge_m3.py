#!/usr/bin/env python3
"""
Reindexe toutes les memoires avec BAAI/bge-m3 (1024D).

EPIC-48 Story 48.3 — Semantic Search Optimization

Workflow:
1. Charge BGE-M3 via SentenceTransformer
2. Parcourt les memoires par lots de 100 (WHERE embedding IS NULL)
3. Genere embeddings 1024D + halfvec
4. UPDATE memories SET embedding, embedding_half, embedding_model
5. Log progression toutes les 1000 memoires

Performance:
- 37K memoires x 100/batch x ~2s/batch ≈ 12-15 minutes
- Modele BGE-M3: ~2.2 GB, temps de chargement ~30s
- Reprise automatique: WHERE embedding IS NULL ignore les memoires deja indexees

Usage:
    python3 scripts/reindex_bge_m3.py
"""

import asyncio
import os
import sys
import time

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

# --- Configuration ---
MODEL_NAME = "BAAI/bge-m3"
BATCH_SIZE = 100
LOG_INTERVAL = 1000

DB_USER = os.getenv("POSTGRES_USER", "mnemo")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "mnemo")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "mnemolite")

DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

DOC_PREFIX = "Represent this passage for retrieval: "


async def main():
    print(f"BGE-M3 Reindexing — EPIC-48 Story 48.3")
    print(f"Model: {MODEL_NAME}")
    print(f"DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Batch size: {BATCH_SIZE}")
    print()

    # 1. Load model
    print("Loading BGE-M3 model (~2.2 GB, ~30s)...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # 2. Connect to DB
    engine = create_async_engine(DB_URL)

    async with engine.connect() as conn:
        # 3. Count memories to reindex
        total = (await conn.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL")
        )).scalar()

        if total == 0:
            print("All memories already have embeddings. Nothing to do.")
            return

        print(f"Memories to reindex: {total}")
        print(f"Estimated time: {total / BATCH_SIZE * 2 / 60:.0f} minutes")
        print()

        # 4. Reindex in batches
        offset = 0
        batch_num = 0
        start_time = time.time()

        while offset < total:
            batch_start = time.time()

            # Fetch batch
            rows = (await conn.execute(
                text("""
                    SELECT id, content
                    FROM memories
                    WHERE embedding IS NULL
                    ORDER BY created_at
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": BATCH_SIZE, "offset": offset}
            )).fetchall()

            if not rows:
                break

            ids = [r[0] for r in rows]
            texts = [f"{DOC_PREFIX}{r[1] or ''}" for r in rows]

            # Encode batch
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            # Update DB in transaction
            async with conn.begin():
                for mem_id, emb in zip(ids, embeddings):
                    half = emb.astype(np.float16)
                    await conn.execute(
                        text("""
                            UPDATE memories
                            SET embedding = CAST(:emb AS vector),
                                embedding_half = CAST(:half AS halfvec),
                                embedding_model = :model
                            WHERE id = :id
                        """),
                        {
                            "emb": emb.tolist(),
                            "half": half.tolist(),
                            "model": MODEL_NAME,
                            "id": mem_id,
                        }
                    )

            offset += BATCH_SIZE
            batch_num += 1
            batch_time = time.time() - batch_start

            # Progress
            pct = min(100, 100 * offset / total)
            indexed = min(offset, total)
            elapsed = time.time() - start_time
            rate = indexed / elapsed if elapsed > 0 else 0
            eta = (total - indexed) / rate if rate > 0 else 0

            if batch_num % (LOG_INTERVAL // BATCH_SIZE) == 0 or offset >= total:
                print(
                    f"  {indexed}/{total} ({pct:.1f}%) | "
                    f"{rate:.0f} docs/s | "
                    f"ETA: {eta/60:.0f}min"
                )

        # 5. Done
        total_time = time.time() - start_time
        print()
        print(f"Reindexation terminee!")
        print(f"  Total: {min(offset, total)} memoires")
        print(f"  Time: {total_time/60:.1f} minutes")
        print(f"  Rate: {min(offset, total)/total_time:.0f} docs/s")

        # Verify
        remaining = (await conn.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL")
        )).scalar()
        if remaining > 0:
            print(f"  ⚠️  {remaining} memoires still without embeddings")
        else:
            print(f"  ✅ All memories have embeddings")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
