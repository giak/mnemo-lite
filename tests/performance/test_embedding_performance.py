"""
Tests de performance pour le service d'embeddings Sentence-Transformers.
Vérifie que les SLAs de latence sont respectés.
"""

import pytest
import time
import statistics
import numpy as np
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService


@pytest.mark.performance
class TestEmbeddingLatency:
    """Tests de latence pour génération d'embeddings."""

    @pytest.mark.asyncio
    async def test_embedding_generation_latency(self):
        """
        Test que la génération d'embedding respecte les SLA de latence.
        """
        service = SentenceTransformerEmbeddingService()

        # Warm-up (charger modèle)
        await service.generate_embedding("warm up")

        # Test cases avec différentes longueurs
        test_cases = [
            ("short", "Hello world", 50),  # max 50ms
            ("medium", "This is a longer paragraph with more words to encode", 100),  # max 100ms
            ("long", "Lorem ipsum " * 50, 200),  # max 200ms
        ]

        latencies = []

        for name, text, max_latency_ms in test_cases:
            start = time.perf_counter()
            embedding = await service.generate_embedding(text)
            elapsed_ms = (time.perf_counter() - start) * 1000

            latencies.append(elapsed_ms)

            assert elapsed_ms < max_latency_ms, (
                f"{name}: {elapsed_ms:.1f}ms > {max_latency_ms}ms (SLA breach)"
            )
            assert len(embedding) == 768, "Wrong dimension"

        # Log statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = np.percentile(latencies, 95) if len(latencies) > 1 else latencies[0]

        print(f"\nLatency Statistics:")
        print(f"  Average: {avg_latency:.1f}ms")
        print(f"  P95: {p95_latency:.1f}ms")

    @pytest.mark.asyncio
    async def test_batch_encoding_faster_than_sequential(self):
        """
        Test que le batch encoding est plus rapide que N appels séquentiels.
        """
        service = SentenceTransformerEmbeddingService()

        texts = [
            "First text to encode",
            "Second text to encode",
            "Third text to encode",
            "Fourth text to encode",
            "Fifth text to encode",
        ]

        # Warm-up
        await service.generate_embedding("warm up")

        # Sequential encoding
        start_seq = time.perf_counter()
        for text in texts:
            await service.generate_embedding(text)
        time_seq_ms = (time.perf_counter() - start_seq) * 1000

        # Batch encoding
        start_batch = time.perf_counter()
        await service.generate_embeddings_batch(texts)
        time_batch_ms = (time.perf_counter() - start_batch) * 1000

        # Batch should be at least 2x faster
        speedup = time_seq_ms / time_batch_ms

        print(f"\nBatch Encoding Performance:")
        print(f"  Sequential: {time_seq_ms:.1f}ms")
        print(f"  Batch: {time_batch_ms:.1f}ms")
        print(f"  Speedup: {speedup:.2f}x")

        assert speedup > 1.5, (
            f"Batch encoding should be >1.5x faster, got {speedup:.2f}x"
        )


@pytest.mark.performance
class TestCachePerformance:
    """Tests de performance du cache LRU."""

    @pytest.mark.asyncio
    async def test_embedding_cache_effectiveness(self):
        """
        Test que le cache améliore significativement les performances.
        """
        service = SentenceTransformerEmbeddingService(cache_size=100)

        text = "Test text for caching"

        # Warm-up
        await service.generate_embedding("warm up")

        # First call (cache miss)
        start1 = time.perf_counter()
        emb1 = await service.generate_embedding(text)
        time1_ms = (time.perf_counter() - start1) * 1000

        # Second call (cache hit)
        start2 = time.perf_counter()
        emb2 = await service.generate_embedding(text)
        time2_ms = (time.perf_counter() - start2) * 1000

        # Assertions
        assert emb1 == emb2, "Cached result should be identical"
        assert time2_ms < time1_ms / 10, (
            f"Cache should be 10x+ faster (got {time1_ms/time2_ms:.1f}x)"
        )
        assert time2_ms < 1, f"Cache hit should be < 1ms (got {time2_ms:.1f}ms)"

        # Verify cache stats
        stats = service.get_stats()
        assert stats["cache_size"] > 0, "Cache should contain entries"
        assert stats["cache_enabled"], "Cache should be enabled"

        print(f"\nCache Performance:")
        print(f"  Cache miss: {time1_ms:.2f}ms")
        print(f"  Cache hit: {time2_ms:.2f}ms")
        print(f"  Speedup: {time1_ms/time2_ms:.1f}x")
        print(f"  Cache size: {stats['cache_size']}/{stats['cache_max_size']}")

    @pytest.mark.asyncio
    async def test_cache_hit_rate_with_repeated_queries(self):
        """
        Test le taux de hit du cache avec des queries répétées.
        """
        service = SentenceTransformerEmbeddingService(cache_size=50)

        # Warm-up
        await service.generate_embedding("warm up")

        # Simulate user queries (some repeated)
        queries = [
            "search for cats",
            "find dogs",
            "search for cats",  # Repeated
            "show me cars",
            "find dogs",  # Repeated
            "search for cats",  # Repeated
        ]

        latencies = []

        for query in queries:
            start = time.perf_counter()
            await service.generate_embedding(query)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        # Repeated queries should be much faster
        first_cat = latencies[0]
        second_cat = latencies[2]
        third_cat = latencies[5]

        # Second and third calls should be cache hits (< 1ms)
        assert second_cat < 1, f"Second 'cats' query should be cached, got {second_cat:.2f}ms"
        assert third_cat < 1, f"Third 'cats' query should be cached, got {third_cat:.2f}ms"

        print(f"\nCache Hit Rate Test:")
        print(f"  First 'cats': {first_cat:.2f}ms (miss)")
        print(f"  Second 'cats': {second_cat:.2f}ms (hit)")
        print(f"  Third 'cats': {third_cat:.2f}ms (hit)")


@pytest.mark.performance
class TestThroughput:
    """Tests de débit (throughput)."""

    @pytest.mark.asyncio
    async def test_sustained_throughput(self):
        """
        Test le débit soutenu sur 100 encodings.
        """
        service = SentenceTransformerEmbeddingService(cache_size=0)  # Disable cache

        # Warm-up
        await service.generate_embedding("warm up")

        # Generate 100 embeddings
        num_encodings = 100
        texts = [f"Test query number {i}" for i in range(num_encodings)]

        start = time.perf_counter()

        for text in texts:
            await service.generate_embedding(text)

        elapsed_sec = time.perf_counter() - start

        throughput = num_encodings / elapsed_sec
        avg_latency_ms = (elapsed_sec / num_encodings) * 1000

        print(f"\nSustained Throughput:")
        print(f"  Total time: {elapsed_sec:.2f}s")
        print(f"  Throughput: {throughput:.1f} encodings/sec")
        print(f"  Average latency: {avg_latency_ms:.1f}ms")

        # Should encode at least 10 texts per second
        assert throughput > 10, (
            f"Throughput too low: {throughput:.1f} encodings/sec"
        )
