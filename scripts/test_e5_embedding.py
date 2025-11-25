#!/usr/bin/env python3
"""
Quick test: Validate multilingual-e5-base integration.

Usage (inside Docker container):
    docker compose exec api python scripts/test_e5_embedding.py
"""

import asyncio
import sys
import time

sys.path.insert(0, '/app')


async def main():
    from services.sentence_transformer_embedding_service import (
        SentenceTransformerEmbeddingService,
        TextType,
        EMBEDDING_MODELS,
    )
    import numpy as np

    print("=" * 60)
    print("Testing multilingual-e5-base integration")
    print("=" * 60)

    # Show available models
    print("\nAvailable models:")
    for name, config in EMBEDDING_MODELS.items():
        print(f"  - {name}: {config['dimension']}D, uses_prefix={config.get('uses_prefix', False)}")

    # Test E5-base
    model_name = "intfloat/multilingual-e5-base"
    print(f"\n{'='*60}")
    print(f"Loading: {model_name}")
    print("=" * 60)

    start = time.time()
    service = SentenceTransformerEmbeddingService(model_name=model_name)

    # Warm up (loads model)
    _ = await service.embed_query("warmup")
    load_time = time.time() - start

    print(f"Load time: {load_time:.2f}s")
    print(f"Model config: {service.model_config}")

    # Test French queries
    test_queries = [
        "Jordan Bardella Rassemblement National",
        "accord UE-Mercosur agriculture",
    ]

    test_docs = [
        "Jordan Bardella, président du RN, critique l'accord UE-Mercosur.",
        "Les agriculteurs français manifestent contre les importations.",
    ]

    print("\n--- Testing query embedding (should add 'query: ' prefix) ---")
    for query in test_queries:
        start = time.time()
        emb = await service.embed_query(query)
        elapsed = (time.time() - start) * 1000
        print(f"  Query: '{query[:40]}...' -> {len(emb)}D [{elapsed:.1f}ms]")

    print("\n--- Testing document embedding (should add 'passage: ' prefix) ---")
    for doc in test_docs:
        start = time.time()
        emb = await service.embed_document(doc)
        elapsed = (time.time() - start) * 1000
        print(f"  Doc: '{doc[:40]}...' -> {len(emb)}D [{elapsed:.1f}ms]")

    # Test similarity
    print("\n--- Testing similarity (query vs docs) ---")
    query_emb = await service.embed_query("Bardella critique le commerce")

    for doc in test_docs:
        doc_emb = await service.embed_document(doc)
        sim = await service.compute_similarity(query_emb, doc_emb)
        print(f"  '{doc[:50]}...' -> similarity: {sim:.3f}")

    print("\n" + "=" * 60)
    print("✅ E5-base integration test PASSED")
    print("=" * 60)
    print(f"\nTo use E5-base in production, set:")
    print('  EMBEDDING_MODEL="intfloat/multilingual-e5-base"')
    print("\nNote: First load downloads ~1.1GB model")


if __name__ == "__main__":
    asyncio.run(main())
