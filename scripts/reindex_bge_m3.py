#!/usr/bin/env python3
"""
Reindexe toutes les memoires avec BAAI/bge-m3 (1024D).

EPIC-48 Story 48.3 — Semantic Search Optimization

Connexion DB (ordre de priorite) :
1. DATABASE_URL (meme variable que l'API — fonctionnement garanti)
2. POSTGRES_HOST/USER/PASSWORD/DB/PORT (fallback avec operateur 'or' pour chaines vides)

Workflow:
1. Charge BGE-M3 via SentenceTransformer
2. Pagination par curseur (WHERE id > last_id AND embedding IS NULL)
3. Genere embeddings 1024D + halfvec par lots de 100
4. UPDATE en transaction par lot (commits atomiques)
5. Log progression toutes les 1000 memoires

Reprise automatique : WHERE embedding IS NULL ignore les memoires deja indexees.

Usage:
    # PyTorch FP32 (default)
    python3 scripts/reindex_bge_m3.py

    # ONNX INT8 (2.5x faster, same quality, direct onnxruntime — no optimum needed)
    USE_ONNX=true python3 scripts/reindex_bge_m3.py
"""

import asyncio
import os
import sys
import time
import traceback

# sqlalchemy imported lazily in _main()
# sqlalchemy imported lazily in _main()

# --- Configuration ---
MODEL_NAME = "BAAI/bge-m3"
ONNX_MODEL_PATH = "/app/models/bge-m3-onnx-int8"  # Pre-exported ONNX INT8 model (EPIC-48)
USE_ONNX = os.environ.get("USE_ONNX", "").lower() in ("true", "1", "yes")
BATCH_SIZE = 25
MAX_CONTENT_LENGTH = 2000  # Truncate before encoding (tokenizer is O(n) on input length)
LOG_INTERVAL = 25  # Log every batch

DOC_PREFIX = "Represent this passage for retrieval: "


def build_db_url() -> str:
    """Construit l'URL de connexion DB de maniere robuste.

    Priorite 1 : DATABASE_URL (meme variable que l'API — garantie de fonctionner)
    Priorite 2 : POSTGRES_* individuelles (fallback avec 'or' pour chaines vides)
    """
    # Priorite 1 : DATABASE_URL
    db_url = os.environ.get("DATABASE_URL") or ""
    if db_url:
        print(f"Using DATABASE_URL from environment")
        # Mask password for logging
        masked = db_url
        if "@" in masked:
            parts = masked.split("@")
            if ":" in parts[0]:
                user_host = parts[0].rsplit(":", 1)
                if len(user_host) == 2:
                    masked = f"{user_host[0]}:****@{parts[1]}"
        print(f"  URL: {masked}")
        return db_url

    # Priorite 2 : POSTGRES_* individuelles (avec 'or' pour chaines vides)
    user = os.environ.get("POSTGRES_USER") or "mnemo"
    password = os.environ.get("POSTGRES_PASSWORD") or "mnemo"
    host = os.environ.get("POSTGRES_HOST") or "db"
    port = os.environ.get("POSTGRES_PORT") or "5432"
    dbname = os.environ.get("POSTGRES_DB") or "mnemolite"

    print(f"Building DB URL from POSTGRES_* vars:")
    print(f"  User: {user}")
    print(f"  Password: {'***' if password else '(empty)'}")
    print(f"  Host: {host}:{port}")
    print(f"  DB: {dbname}")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"




class OnnxEmbedder:
    """Minimal ONNX embedder using onnxruntime directly (no optimum needed).
    
    Bypasses optimum/torch version conflicts. Uses CLS pooling + L2 norm
    to match SentenceTransformer BGE-M3 behavior exactly.
    """
    
    def __init__(self, model_path: str):
        import onnxruntime as ort
        from transformers import AutoTokenizer
        
        onnx_file = os.path.join(model_path, "onnx", "model.onnx")
        if not os.path.exists(onnx_file):
            raise FileNotFoundError(f"ONNX model not found at {onnx_file}")
        
        self.session = ort.InferenceSession(onnx_file, providers=['CPUExecutionProvider'])
        self.tokenizer = AutoTokenizer.from_pretrained(
            os.path.join(model_path, "onnx")
        )
    
    def encode(self, texts: list, normalize_embeddings: bool = True,
               show_progress_bar: bool = False, batch_size: int = 25):
        """Encode texts to embeddings. API-compatible with SentenceTransformer.encode()."""
        import numpy as np
        
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=8192,  # BGE-M3 native max (no extra truncation beyond MAX_CONTENT_LENGTH)
                return_tensors='np'
            )
            
            # Run ONNX inference
            outputs = self.session.run(None, {
                'input_ids': inputs['input_ids'],
                'attention_mask': inputs['attention_mask'],
            })
            hidden = outputs[0]  # (batch, seq_len, 1024)
            
            # CLS pooling (first token = <s>)
            embeddings = hidden[:, 0, :]
            
            if normalize_embeddings:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / np.maximum(norms, 1e-12)
            
            all_embeddings.append(embeddings)
        
        return np.concatenate(all_embeddings, axis=0)

async def main():
    try:
        await _main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


async def _main():
    import numpy as np
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.sql import text

    print(f"BGE-M3 Reindexing — EPIC-48 Story 48.3")
    backend = "ONNX INT8" if USE_ONNX else "PyTorch FP32"
    model_path = ONNX_MODEL_PATH if USE_ONNX else MODEL_NAME
    print(f"Model: {model_path}")
    print(f"Backend: {backend}")
    print()

    # 1. Build DB URL
    DB_URL = build_db_url()
    print()

    # 2. Load model
    if USE_ONNX:
        print(f"Loading BGE-M3 ONNX INT8 model from {ONNX_MODEL_PATH}...")
        print("  (2.5x faster than PyTorch FP32 on CPU, direct onnxruntime)")
        t0 = time.time()
        model = OnnxEmbedder(ONNX_MODEL_PATH)
        print(f"Model loaded in {time.time() - t0:.1f}s")
    else:
        from sentence_transformers import SentenceTransformer
        print("Loading BGE-M3 model (~2.2 GB, ~30s)...")
        t0 = time.time()
        model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
        print(f"Model loaded in {time.time() - t0:.1f}s")
    sys.stdout.flush()

    # 3. Connect to DB
    print(f"Connecting to database...")
    engine = create_async_engine(DB_URL)

    async with engine.connect() as conn:
        # Test connection
        await conn.execute(text("SELECT 1"))
        print("Connected.")
        print()

        # 4. Count memories to reindex
        total = (await conn.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL")
        )).scalar()

        if total == 0:
            print("All memories already have embeddings. Nothing to do.")
            return

        print(f"Memories to reindex: {total}")
        print(f"Batch size: {BATCH_SIZE}")
        print(f"Estimated time: {max(1, total / BATCH_SIZE * 2 / 60):.0f} minutes")
        print()
        sys.stdout.flush()

        # 5. Reindex — cursor-based pagination (resilient to concurrent changes)
        last_id = ""  # empty string = start from beginning
        indexed = 0
        batch_num = 0
        start_time = time.time()

        while True:
            batch_start = time.time()

            # Fetch batch with cursor pagination
            if not last_id:
                rows = (await conn.execute(
                    text("""
                        SELECT id, content
                        FROM memories
                        WHERE embedding IS NULL
                        ORDER BY id
                        LIMIT :limit
                    """),
                    {"limit": BATCH_SIZE}
                )).fetchall()
            else:
                rows = (await conn.execute(
                    text("""
                        SELECT id, content
                        FROM memories
                        WHERE embedding IS NULL AND id > :last_id
                        ORDER BY id
                        LIMIT :limit
                    """),
                    {"limit": BATCH_SIZE, "last_id": last_id}
                )).fetchall()

            if not rows:
                break

            ids = [r[0] for r in rows]
            # Truncate long content: tokenizer time scales linearly with input length
            # 2M char docs would take hours without this
            texts = [f"{DOC_PREFIX}{(r[1] or '')[:MAX_CONTENT_LENGTH]}" for r in rows]
            last_id = ids[-1]

            # Encode batch
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            # Update DB in transaction — bulk executemany (1 round-trip vs 100)
            async with engine.begin() as txn:
                import numpy as np
                params = [
                    {
                        "emb": str(emb.tolist()),
                        "half": str(emb.astype(np.float16).tolist()),
                        "model": MODEL_NAME,
                        "id": mem_id,
                    }
                    for mem_id, emb in zip(ids, embeddings)
                ]
                await txn.execute(
                    text("""
                        UPDATE memories
                        SET embedding = CAST(:emb AS vector),
                            embedding_half = CAST(:half AS halfvec),
                            embedding_model = :model
                        WHERE id = :id
                    """),
                    params,
                )

            indexed += len(rows)
            batch_num += 1
            batch_time = time.time() - batch_start

            # Progress
            pct = min(100, 100 * indexed / total) if total else 0
            elapsed = time.time() - start_time
            rate = indexed / elapsed if elapsed > 0 else 0
            eta = (total - indexed) / rate if rate > 0 else 0

            if batch_num % (LOG_INTERVAL // BATCH_SIZE) == 0 or indexed >= total:
                print(
                    f"  {indexed}/{total} ({pct:.1f}%) | "
                    f"Batch: {batch_time:.1f}s | "
                    f"Rate: {rate:.0f} docs/s | "
                    f"ETA: {eta/60:.0f}min"
                )
                sys.stdout.flush()

        # 6. Done
        total_time = time.time() - start_time
        print()
        print(f"Reindexation terminee!")
        print(f"  Total: {indexed} memoires")
        print(f"  Time: {total_time/60:.1f} minutes")
        print(f"  Rate: {indexed/total_time:.0f} docs/s" if total_time > 0 else "")

        # Verify
        remaining = (await conn.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL")
        )).scalar()
        if remaining > 0:
            print(f"  WARNING: {remaining} memoires still without embeddings")
        else:
            print(f"  OK: All memories have embeddings")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
