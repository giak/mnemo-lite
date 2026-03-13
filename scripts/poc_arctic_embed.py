#!/usr/bin/env python3
"""
POC: Compare Nomic Embed v1.5 vs Snowflake Arctic-Embed-M v2.0

EPIC-24: Tests potential upgrade to Arctic-Embed for better CPU performance.

Key differences:
- nomic-embed-text-v1.5: 137M params, 768D, ~159ms/query
- snowflake-arctic-embed-m-v2.0: 110M params, 768D, multilingual, Apache 2.0

Expected improvements:
- 4-6x faster inference on CPU
- Better MTEB scores (54.90 vs 53.25 NDCG@10)
- Native multilingual support (important for French)

Usage (inside Docker container):
    docker compose exec api python scripts/poc_arctic_embed.py
"""

import asyncio
import sys
import os
import time
import tracemalloc

sys.path.insert(0, '/app')

# Test queries (French - good test for multilingual)
TEST_QUERIES = [
    # French political terms
    "Jordan Bardella Rassemblement National",
    "accord UE-Mercosur agriculture",
    "élections européennes 2024 stratégie",

    # Mixed language (multilingual test)
    "Mercosur trade agreement farmers",
    "souverainisme économique commerce",

    # Semantic queries
    "contradiction entre discours et votes",
    "hypocrisie politique agriculture",
]

# Sample documents (French)
TEST_DOCUMENTS = [
    "Jordan Bardella, président du RN, critique l'accord UE-Mercosur.",
    "Les agriculteurs français manifestent contre les importations de boeuf.",
    "Marine Le Pen s'oppose à la Commission européenne sur le commerce.",
    "Investigation sur la stratégie électorale du Rassemblement National.",
]

# Models to test
MODELS = {
    "nomic-ai/nomic-embed-text-v1.5": {
        "name": "Nomic v1.5",
        "params": "137M",
        "query_instruction": None,
    },
    "BAAI/bge-base-en-v1.5": {
        "name": "BGE-base v1.5",
        "params": "110M",
        "query_instruction": "Represent this sentence for searching relevant passages: ",
    },
    "sentence-transformers/all-MiniLM-L6-v2": {
        "name": "MiniLM-L6-v2",
        "params": "22M",
        "query_instruction": None,
    },
}


async def test_model(model_name: str, config: dict):
    """Test a specific model's performance."""
    from sentence_transformers import SentenceTransformer
    import numpy as np

    print(f"\n{'='*60}")
    print(f"Testing: {config['name']} ({config['params']})")
    print(f"Model: {model_name}")
    print(f"{'='*60}")

    # Start memory tracking
    tracemalloc.start()
    mem_before = tracemalloc.get_traced_memory()[0] / 1024 / 1024

    # Load model
    load_start = time.time()
    try:
        model = SentenceTransformer(model_name, device="cpu", trust_remote_code=True)
    except Exception as e:
        print(f"  ERROR loading model: {e}")
        tracemalloc.stop()
        return None

    load_time = time.time() - load_start
    mem_after_load = tracemalloc.get_traced_memory()[0] / 1024 / 1024

    print(f"Load time: {load_time:.2f}s")
    print(f"RAM used: {mem_after_load - mem_before:.1f} MB")
    print(f"Embedding dimension: {model.get_sentence_embedding_dimension()}")

    # Embed documents
    print("\nEmbedding documents...")
    doc_start = time.time()
    doc_embeddings = model.encode(TEST_DOCUMENTS, convert_to_numpy=True)
    doc_time = (time.time() - doc_start) * 1000
    print(f"  {len(TEST_DOCUMENTS)} documents in {doc_time:.1f}ms ({doc_time/len(TEST_DOCUMENTS):.1f}ms/doc)")

    # Test queries
    print("\nQuery-Document Similarities:")
    print("-" * 60)

    total_query_time = 0
    all_scores = []
    query_instruction = config.get("query_instruction", "")

    for query in TEST_QUERIES:
        # Add instruction for Arctic if needed
        query_text = f"{query_instruction}{query}" if query_instruction else query

        query_start = time.time()
        query_emb = model.encode(query_text, convert_to_numpy=True)
        query_time = (time.time() - query_start) * 1000
        total_query_time += query_time

        # Compute similarities
        similarities = []
        for doc_emb in doc_embeddings:
            sim = np.dot(query_emb, doc_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(doc_emb))
            similarities.append(sim)

        max_sim = max(similarities)
        max_idx = similarities.index(max_sim)
        all_scores.append(max_sim)

        print(f"  '{query[:40]:<40}' -> max={max_sim:.3f} (doc {max_idx}) [{query_time:.1f}ms]")

    avg_time = total_query_time / len(TEST_QUERIES)
    avg_score = sum(all_scores) / len(all_scores)

    mem_final = tracemalloc.get_traced_memory()[1] / 1024 / 1024  # Peak memory
    tracemalloc.stop()

    print()
    print(f"Average query time: {avg_time:.1f}ms")
    print(f"Average max similarity: {avg_score:.3f}")
    print(f"Peak RAM: {mem_final:.1f} MB")

    return {
        "model": model_name,
        "name": config["name"],
        "params": config["params"],
        "load_time_s": load_time,
        "avg_query_time_ms": avg_time,
        "avg_max_similarity": avg_score,
        "ram_mb": mem_final,
        "dimension": model.get_sentence_embedding_dimension(),
    }


async def main():
    print("=" * 70)
    print("POC: Nomic v1.5 vs Snowflake Arctic-Embed-M v2.0")
    print("EPIC-24: Testing CPU-optimized embedding model upgrade")
    print("=" * 70)

    results = []

    for model_name, config in MODELS.items():
        result = await test_model(model_name, config)
        if result:
            results.append(result)

    if len(results) < 2:
        print("\n⚠️  Could not test multiple models. Check errors above.")
        return

    print()
    print("=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print()

    # Header
    headers = ["Metric"] + [r["name"] for r in results]
    col_width = 15
    print(f"{'Metric':<20}", end=" | ")
    for r in results:
        print(f"{r['name']:>{col_width}}", end=" | ")
    print()
    print("-" * 80)

    # Load time
    print(f"{'Load time (s)':<20}", end=" | ")
    for r in results:
        print(f"{r['load_time_s']:>{col_width}.2f}", end=" | ")
    print()

    # Query time
    print(f"{'Query time (ms)':<20}", end=" | ")
    for r in results:
        print(f"{r['avg_query_time_ms']:>{col_width}.1f}", end=" | ")
    print()

    # Similarity
    print(f"{'Avg similarity':<20}", end=" | ")
    for r in results:
        print(f"{r['avg_max_similarity']:>{col_width}.3f}", end=" | ")
    print()

    # RAM
    print(f"{'Peak RAM (MB)':<20}", end=" | ")
    for r in results:
        print(f"{r['ram_mb']:>{col_width}.1f}", end=" | ")
    print()

    # Dimension
    print(f"{'Dimension':<20}", end=" | ")
    for r in results:
        print(f"{r['dimension']:>{col_width}}", end=" | ")
    print()

    print()
    print("=" * 80)
    print("ANALYSIS vs Nomic v1.5 (baseline)")
    print("=" * 80)

    baseline = results[0]  # Nomic v1.5

    for r in results[1:]:
        speedup = baseline["avg_query_time_ms"] / r["avg_query_time_ms"]
        quality_ratio = r["avg_max_similarity"] / baseline["avg_max_similarity"]

        print(f"\n{r['name']}:")
        print(f"  Speedup: {speedup:.1f}x {'faster' if speedup > 1 else 'slower'}")
        print(f"  Quality: {quality_ratio*100:.1f}% of baseline")
        print(f"  RAM: {r['ram_mb'] - baseline['ram_mb']:+.1f} MB")

        if speedup > 2 and quality_ratio >= 0.90:
            print(f"  ✅ EXCELLENT: Much faster, quality maintained")
        elif speedup > 1.5 and quality_ratio >= 0.85:
            print(f"  ✅ GOOD: Faster with acceptable quality tradeoff")
        elif speedup > 1.2 and quality_ratio >= 0.80:
            print(f"  ⚠️  CONSIDER: Moderate improvement")
        else:
            print(f"  ❌ NOT RECOMMENDED for this use case")


if __name__ == "__main__":
    asyncio.run(main())
