"""
Benchmark script for CODE model RAM usage (EPIC-06 Phase 1 Story 2).

Measures:
- Baseline RAM (API process without models)
- TEXT model RAM (nomic-embed-text-v1.5)
- CODE model RAM (jina-embeddings-v2-base-code)
- Dual models RAM (TEXT + CODE simultaneously)
- Encoding latency

Decision criteria:
- CODE model RAM < 1.5 GB → OK
- CODE model RAM > 1.5 GB → WARNING (quantization FP16 recommended)
- Dual models RAM > 2 GB → RED FLAG (model swapping or larger container needed)
"""

import asyncio
import time
from pathlib import Path

import psutil
from sentence_transformers import SentenceTransformer


def get_process_ram_mb():
    """Get current process RAM usage in MB."""
    process = psutil.Process()
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024  # RSS = Resident Set Size (actual RAM)


def format_ram(mb):
    """Format RAM size."""
    if mb < 1024:
        return f"{mb:.2f} MB"
    else:
        return f"{mb / 1024:.2f} GB"


async def benchmark_code_model():
    """Benchmark jina-embeddings-v2-base-code model."""

    print("=" * 70)
    print("EPIC-06 Phase 1 Story 2: CODE Model RAM Benchmark")
    print("=" * 70)
    print()

    # Step 1: Baseline RAM
    print("Step 1: Measuring baseline RAM...")
    baseline_mb = get_process_ram_mb()
    print(f"✅ Baseline RAM: {format_ram(baseline_mb)}")
    print()

    # Step 2: Load TEXT model (reference)
    print("Step 2: Loading TEXT model (nomic-embed-text-v1.5)...")
    start = time.time()
    text_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")
    load_time_text = time.time() - start

    text_loaded_mb = get_process_ram_mb()
    text_delta_mb = text_loaded_mb - baseline_mb

    print(f"✅ TEXT model loaded: {format_ram(text_loaded_mb)} (+{format_ram(text_delta_mb)})")
    print(f"   Load time: {load_time_text:.2f}s")
    print()

    # Step 3: Unload TEXT model (clear memory)
    print("Step 3: Unloading TEXT model...")
    del text_model
    import gc
    gc.collect()
    await asyncio.sleep(1)  # Give GC time to clean up

    after_unload_mb = get_process_ram_mb()
    print(f"✅ After TEXT unload: {format_ram(after_unload_mb)}")
    print()

    # Step 4: Load CODE model
    print("Step 4: Loading CODE model (jina-embeddings-v2-base-code)...")
    start = time.time()
    code_model = SentenceTransformer("jinaai/jina-embeddings-v2-base-code")
    load_time_code = time.time() - start

    code_loaded_mb = get_process_ram_mb()
    code_delta_mb = code_loaded_mb - after_unload_mb

    print(f"✅ CODE model loaded: {format_ram(code_loaded_mb)} (+{format_ram(code_delta_mb)})")
    print(f"   Load time: {load_time_code:.2f}s")
    print()

    # Step 5: Benchmark encoding latency
    print("Step 5: Benchmarking encoding latency...")

    code_sample = '''
def calculate_total(items):
    """Calculate total price from items."""
    return sum(item.price for item in items)
'''

    # Warmup
    _ = code_model.encode(code_sample)

    # Measure
    times = []
    for _ in range(10):
        start = time.time()
        embedding = code_model.encode(code_sample)
        elapsed_ms = (time.time() - start) * 1000
        times.append(elapsed_ms)

    avg_latency = sum(times) / len(times)
    p95_latency = sorted(times)[int(0.95 * len(times))]
    embedding_dim = len(embedding)

    print(f"✅ Encoding latency:")
    print(f"   Average: {avg_latency:.2f}ms")
    print(f"   P95: {p95_latency:.2f}ms")
    print(f"   Embedding dimension: {embedding_dim}")
    print()

    # Step 6: Dual loading test (TEXT + CODE simultaneously)
    print("Step 6: Testing dual models (TEXT + CODE simultaneously)...")
    print("   Loading TEXT model again...")
    text_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")

    dual_loaded_mb = get_process_ram_mb()
    dual_delta_mb = dual_loaded_mb - baseline_mb

    print(f"✅ Dual models loaded: {format_ram(dual_loaded_mb)} (+{format_ram(dual_delta_mb)})")
    print()

    # Step 7: Verdict
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    print()

    print(f"📊 RAM Summary:")
    print(f"   Baseline:        {format_ram(baseline_mb)}")
    print(f"   TEXT model:      {format_ram(text_delta_mb)} (overhead)")
    print(f"   CODE model:      {format_ram(code_delta_mb)} (overhead)")
    print(f"   Dual models:     {format_ram(dual_delta_mb)} (total overhead)")
    print()

    print(f"⚡ Performance:")
    print(f"   Encoding latency: {avg_latency:.2f}ms avg, {p95_latency:.2f}ms P95")
    print(f"   Embedding dimension: {embedding_dim} (expected: 768)")
    print()

    # Decision logic
    print("🎯 Decision:")

    if embedding_dim != 768:
        print(f"   ❌ RED FLAG: Embedding dimension {embedding_dim} != 768")
        print(f"      ACTION REQUIRED: Verify jina-code model configuration")
        return False

    if code_delta_mb > 1500:  # 1.5 GB threshold
        print(f"   ⚠️  WARNING: CODE model RAM {format_ram(code_delta_mb)} > 1.5 GB")
        print(f"      RECOMMENDATION: Quantization FP16 or model swapping")
        verdict = "WARNING"
    elif code_delta_mb > 1000:  # 1 GB threshold
        print(f"   ⚠️  CAUTION: CODE model RAM {format_ram(code_delta_mb)} > 1 GB")
        print(f"      RECOMMENDATION: Monitor RAM, test dual loading carefully")
        verdict = "CAUTION"
    else:
        print(f"   ✅ OK: CODE model RAM {format_ram(code_delta_mb)} < 1 GB")
        verdict = "OK"

    print()

    if dual_delta_mb > 2048:  # 2 GB container limit
        print(f"   ⚠️  RED FLAG: Dual models RAM {format_ram(dual_delta_mb)} > 2 GB")
        print(f"      RECOMMENDATION: Model swapping or larger container (2GB → 4GB)")
        verdict = "RED_FLAG"
    elif dual_delta_mb > 1800:
        print(f"   ⚠️  WARNING: Dual models RAM {format_ram(dual_delta_mb)} close to 2 GB limit")
        print(f"      RECOMMENDATION: Use separate domains (TEXT for events, CODE for code_chunks)")
        if verdict == "OK":
            verdict = "WARNING"
    else:
        print(f"   ✅ OK: Dual models RAM {format_ram(dual_delta_mb)} < 2 GB")
        if verdict == "OK":
            verdict = "OK"

    print()
    print("=" * 70)
    print(f"FINAL VERDICT: {verdict}")
    print("=" * 70)
    print()

    # Recommendations based on Phase 0 learnings
    print("📝 Notes from Phase 0:")
    print("   - TEXT model actual RAM: 1.25 GB (vs 260 MB estimated)")
    print("   - Formula: Process RAM = Baseline + (Model Weights × 3-5)")
    print("   - Dual models TEXT+CODE may not fit in 2 GB container")
    print("   - Use cases can be separated: TEXT for events, CODE for code intelligence")
    print()

    return verdict in ["OK", "CAUTION"]


if __name__ == "__main__":
    print("Starting CODE model benchmark...")
    print()

    success = asyncio.run(benchmark_code_model())

    print()
    if success:
        print("✅ Benchmark PASSED")
        exit(0)
    else:
        print("❌ Benchmark FAILED - Review recommendations")
        exit(1)
