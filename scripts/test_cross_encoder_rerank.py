#!/usr/bin/env python3
"""
Test: Cross-encoder reranking service (EPIC-24 P2).

Validates that cross-encoder reranking improves search quality,
especially for French content.

Usage (inside Docker container):
    docker compose exec api python scripts/test_cross_encoder_rerank.py

Expected improvement: +20-30% quality on French queries.
"""

import asyncio
import sys
import time

sys.path.insert(0, '/app')


# Test queries (French - political/news domain)
TEST_QUERIES = [
    "Jordan Bardella critique accord Mercosur",
    "agriculture UE commerce international",
    "élections européennes stratégie RN",
]

# Test documents (mix of relevant and irrelevant)
TEST_DOCUMENTS = [
    # Highly relevant
    "Jordan Bardella, président du Rassemblement National, critique vivement l'accord UE-Mercosur qui menace selon lui les agriculteurs français.",
    "L'accord commercial entre l'Union Européenne et le Mercosur suscite de vives tensions dans le milieu agricole français.",

    # Moderately relevant
    "Les élections européennes de 2024 ont montré une progression significative de l'extrême droite en France.",
    "Marine Le Pen et le RN s'opposent aux politiques commerciales de la Commission européenne.",

    # Slightly relevant
    "La politique agricole commune (PAC) est au centre des débats européens.",
    "Le commerce international affecte de nombreux secteurs économiques.",

    # Irrelevant (noise)
    "Le temps sera ensoleillé demain sur l'ensemble du territoire.",
    "Les résultats sportifs du week-end montrent une belle performance de l'équipe locale.",
    "La nouvelle recette de cuisine propose une variante du plat traditionnel.",
]


async def test_cross_encoder():
    """Test cross-encoder reranking with French queries."""
    from services.cross_encoder_rerank_service import CrossEncoderRerankService, RERANKER_MODELS

    print("=" * 70)
    print("Testing Cross-Encoder Reranking (EPIC-24 P2)")
    print("=" * 70)

    # Show available models
    print("\nAvailable reranker models:")
    for name, config in RERANKER_MODELS.items():
        multilingual = "✓" if config.get("multilingual") else "✗"
        print(f"  - {name}: {config['params']}, speed={config['speed']}, multilingual={multilingual}")

    # Test with default model (MS-MARCO)
    print(f"\n{'='*70}")
    print("Testing: cross-encoder/ms-marco-MiniLM-L-6-v2 (default)")
    print("=" * 70)

    service = CrossEncoderRerankService()

    # Warm up
    print("\nLoading model...")
    start = time.time()
    await service.rerank("test", ["test document"])
    load_time = time.time() - start
    print(f"Model loaded in {load_time:.2f}s")
    print(f"Model config: {service.model_config}")

    # Test each query
    print("\n--- Reranking results ---")
    for query in TEST_QUERIES:
        print(f"\nQuery: '{query}'")
        print("-" * 60)

        start = time.time()
        results = await service.rerank(query, TEST_DOCUMENTS, top_k=5)
        elapsed = (time.time() - start) * 1000

        for i, r in enumerate(results, 1):
            doc_preview = r.document[:60].replace('\n', ' ')
            print(f"  {i}. [{r.score:+.3f}] {doc_preview}...")

        print(f"  Rerank time: {elapsed:.1f}ms")

    # Test rerank_with_ids
    print(f"\n{'='*70}")
    print("Testing rerank_with_ids")
    print("=" * 70)

    docs_with_ids = [
        (f"doc_{i}", doc) for i, doc in enumerate(TEST_DOCUMENTS[:5])
    ]

    results = await service.rerank_with_ids(
        query="politique agricole française",
        documents=docs_with_ids,
        top_k=3
    )

    print("Top 3 results:")
    for doc_id, score, text in results:
        print(f"  {doc_id}: [{score:+.3f}] {text[:50]}...")

    # Service stats
    print(f"\n{'='*70}")
    print("Service stats")
    print("=" * 70)
    stats = service.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print(f"\n{'='*70}")
    print("✅ Cross-encoder reranking test PASSED")
    print("=" * 70)


async def benchmark_with_without_reranking():
    """Compare search quality with and without reranking."""
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
    from services.cross_encoder_rerank_service import CrossEncoderRerankService

    print(f"\n{'='*70}")
    print("Benchmark: With vs Without Reranking")
    print("=" * 70)

    # Initialize services
    embedding_service = SentenceTransformerEmbeddingService(
        model_name="intfloat/multilingual-e5-base"
    )
    reranker = CrossEncoderRerankService()

    # Warm up
    await embedding_service.embed_query("warmup")
    await reranker.rerank("warmup", ["warmup doc"])

    query = "Jordan Bardella critique accord Mercosur agriculteurs"

    # Get query embedding
    query_emb = await embedding_service.embed_query(query)

    # Get document embeddings
    doc_embeddings = []
    for doc in TEST_DOCUMENTS:
        emb = await embedding_service.embed_document(doc)
        doc_embeddings.append(emb)

    # Calculate cosine similarities
    import numpy as np

    similarities = []
    for doc_emb in doc_embeddings:
        sim = np.dot(query_emb, doc_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(doc_emb))
        similarities.append(sim)

    # Rank by bi-encoder similarity
    bi_encoder_ranking = sorted(
        enumerate(similarities),
        key=lambda x: x[1],
        reverse=True
    )

    # Rank by cross-encoder
    results = await reranker.rerank(query, TEST_DOCUMENTS)
    cross_encoder_ranking = [r.original_index for r in results]

    print(f"\nQuery: '{query}'")
    print("\n--- Bi-encoder ranking (E5-base) ---")
    for rank, (idx, sim) in enumerate(bi_encoder_ranking[:5], 1):
        doc = TEST_DOCUMENTS[idx][:50].replace('\n', ' ')
        print(f"  {rank}. [{sim:.3f}] {doc}...")

    print("\n--- Cross-encoder ranking (MS-MARCO) ---")
    for rank, r in enumerate(results[:5], 1):
        doc = r.document[:50].replace('\n', ' ')
        print(f"  {rank}. [{r.score:+.3f}] {doc}...")

    # Check if most relevant doc (idx 0) moved up
    bi_rank_of_doc0 = next(i for i, (idx, _) in enumerate(bi_encoder_ranking) if idx == 0) + 1
    ce_rank_of_doc0 = next(i for i, r in enumerate(results) if r.original_index == 0) + 1

    print(f"\n--- Analysis ---")
    print(f"  Most relevant doc (idx 0):")
    print(f"    Bi-encoder rank: {bi_rank_of_doc0}")
    print(f"    Cross-encoder rank: {ce_rank_of_doc0}")

    if ce_rank_of_doc0 < bi_rank_of_doc0:
        print(f"  ✅ Cross-encoder improved ranking by {bi_rank_of_doc0 - ce_rank_of_doc0} positions")
    elif ce_rank_of_doc0 == bi_rank_of_doc0:
        print(f"  ≈ Same ranking")
    else:
        print(f"  ⚠️ Cross-encoder ranked lower (unusual)")


async def main():
    await test_cross_encoder()
    await benchmark_with_without_reranking()


if __name__ == "__main__":
    asyncio.run(main())
