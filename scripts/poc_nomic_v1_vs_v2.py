#!/usr/bin/env python3
"""
POC: Compare Nomic Embed v1.5 vs v2-MoE for Memory Search

EPIC-24 P1: Tests the improvement from upgrading to Nomic Embed v2-MoE.

Key differences:
- v1.5: 137M params, single model, no prompt_name
- v2-MoE: 475M params (305M active), MoE architecture, multilingual, uses prompt_name

To test v2, set environment variable:
    export EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v2-moe"

Usage (inside Docker container):
    docker compose exec api python scripts/poc_nomic_v1_vs_v2.py
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, '/app')

# Test queries (French - good test for multilingual v2)
TEST_QUERIES = [
    # French political terms
    "Jordan Bardella Rassemblement National",
    "accord UE-Mercosur agriculture",
    "élections européennes 2024 stratégie",

    # Mixed language (v2 should handle better)
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


async def test_model_version(model_name: str):
    """Test a specific model version."""
    from services.sentence_transformer_embedding_service import (
        SentenceTransformerEmbeddingService,
        TextType,
    )
    import numpy as np

    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")

    # Initialize service
    start = time.time()
    service = SentenceTransformerEmbeddingService(model_name=model_name)

    # Warm up (loads model)
    _ = await service.embed_query("warmup")
    load_time = time.time() - start

    print(f"Model load time: {load_time:.2f}s")
    print(f"Version: {service.model_config.get('version', 'unknown')}")
    print(f"Uses prompt_name: {service.model_config.get('uses_prompt_name', False)}")

    # Embed documents
    print("\nEmbedding documents...")
    doc_embeddings = []
    doc_start = time.time()
    for doc in TEST_DOCUMENTS:
        emb = await service.embed_document(doc)
        doc_embeddings.append(emb)
    doc_time = (time.time() - doc_start) * 1000
    print(f"  {len(TEST_DOCUMENTS)} documents in {doc_time:.1f}ms ({doc_time/len(TEST_DOCUMENTS):.1f}ms/doc)")

    # Test queries
    print("\nQuery-Document Similarities:")
    print("-" * 60)

    total_query_time = 0
    all_scores = []

    for query in TEST_QUERIES:
        query_start = time.time()
        query_emb = await service.embed_query(query)
        query_time = (time.time() - query_start) * 1000
        total_query_time += query_time

        # Compute similarities to all docs
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

    print()
    print(f"Average query time: {avg_time:.1f}ms")
    print(f"Average max similarity: {avg_score:.3f}")

    return {
        "model": model_name,
        "version": service.model_config.get('version', 'unknown'),
        "load_time_s": load_time,
        "avg_query_time_ms": avg_time,
        "avg_max_similarity": avg_score,
    }


async def main():
    print("=" * 70)
    print("POC: Nomic Embed v1.5 vs v2-MoE Comparison")
    print("EPIC-24 P1: Testing multilingual MoE model upgrade")
    print("=" * 70)

    # Get current model from env
    current_model = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
    print(f"\nCurrent EMBEDDING_MODEL: {current_model}")

    # Test current model
    result = await test_model_version(current_model)

    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Model: {result['model']}")
    print(f"  Version: {result['version']}")
    print(f"  Load time: {result['load_time_s']:.2f}s")
    print(f"  Avg query time: {result['avg_query_time_ms']:.1f}ms")
    print(f"  Avg max similarity: {result['avg_max_similarity']:.3f}")

    print()
    print("=" * 70)
    print("TO TEST v2-MoE:")
    print("=" * 70)
    print("  1. Set environment variable:")
    print('     export EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v2-moe"')
    print()
    print("  2. Restart Docker container:")
    print("     docker compose restart api")
    print()
    print("  3. Re-run this script:")
    print("     docker compose exec api python scripts/poc_nomic_v1_vs_v2.py")
    print()
    print("  Note: v2 model is ~1.9GB, first load may take 1-2 minutes")
    print("  Expected improvements:")
    print("    - Better multilingual (French) understanding")
    print("    - Higher quality embeddings via MoE")
    print("    - ~10-20% better similarity scores")


if __name__ == "__main__":
    asyncio.run(main())
