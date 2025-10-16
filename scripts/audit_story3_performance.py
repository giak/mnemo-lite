#!/usr/bin/env python3
"""
Audit Story 3 - Performance Benchmarks.

Mesure la performance de la metadata extraction sur différentes tailles de code.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from services.code_chunking_service import CodeChunkingService


def generate_python_code(num_functions: int, avg_lines_per_function: int = 15) -> str:
    """Generate Python code with specified number of functions."""
    functions = []

    for i in range(num_functions):
        func = f'''
def function_{i}(x: int, y: int, z: int = 0) -> int:
    """Function {i} with type hints and docstring.

    Args:
        x: First parameter
        y: Second parameter
        z: Third parameter (default 0)

    Returns:
        Computed result
    """
    result = 0
    for j in range(5):
        if j % 2 == 0:
            result += x
        elif j % 3 == 0:
            result += y
        else:
            result += z
    return abs(result)
'''
        functions.append(func)

    return '\n'.join(functions)


async def benchmark_performance():
    """Run performance benchmarks."""

    service = CodeChunkingService(max_workers=4)

    print("=" * 80)
    print("AUDIT STORY 3 - PERFORMANCE BENCHMARKS")
    print("=" * 80)
    print()

    benchmarks = [
        ("Small file (10 functions, ~150 LOC)", 10),
        ("Medium file (50 functions, ~750 LOC)", 50),
        ("Large file (100 functions, ~1500 LOC)", 100),
        ("Very large file (200 functions, ~3000 LOC)", 200),
    ]

    results = []

    for description, num_funcs in benchmarks:
        print(f"{'=' * 80}")
        print(f"BENCHMARK: {description}")
        print(f"{'=' * 80}")

        source_code = generate_python_code(num_funcs)
        lines = len(source_code.split('\n'))
        chars = len(source_code)

        print(f"Generated: {num_funcs} functions, {lines} lines, {chars:,} characters")
        print()

        # Benchmark WITHOUT metadata
        print("1. Chunking WITHOUT metadata extraction...")
        start = time.time()
        chunks_no_meta = await service.chunk_code(
            source_code=source_code,
            language="python",
            file_path="test.py",
            extract_metadata=False
        )
        time_no_meta = (time.time() - start) * 1000
        print(f"   Time: {time_no_meta:.2f}ms")
        print(f"   Chunks: {len(chunks_no_meta)}")
        print(f"   Throughput: {lines / (time_no_meta / 1000):.0f} LOC/sec")
        print()

        # Benchmark WITH metadata
        print("2. Chunking WITH metadata extraction...")
        start = time.time()
        chunks_with_meta = await service.chunk_code(
            source_code=source_code,
            language="python",
            file_path="test.py",
            extract_metadata=True
        )
        time_with_meta = (time.time() - start) * 1000
        print(f"   Time: {time_with_meta:.2f}ms")
        print(f"   Chunks: {len(chunks_with_meta)}")
        print(f"   Throughput: {lines / (time_with_meta / 1000):.0f} LOC/sec")
        print()

        # Calculate overhead
        overhead_ms = time_with_meta - time_no_meta
        overhead_pct = (overhead_ms / time_no_meta) * 100 if time_no_meta > 0 else 0

        print(f"3. Metadata extraction overhead:")
        print(f"   Absolute: +{overhead_ms:.2f}ms")
        print(f"   Relative: +{overhead_pct:.1f}%")
        print(f"   Per function: {overhead_ms / num_funcs:.2f}ms")
        print()

        # Verify metadata quality
        chunks_with_metadata = sum(1 for c in chunks_with_meta if "signature" in c.metadata)
        metadata_coverage = (chunks_with_metadata / len(chunks_with_meta)) * 100 if chunks_with_meta else 0

        print(f"4. Metadata quality:")
        print(f"   Coverage: {chunks_with_metadata}/{len(chunks_with_meta)} chunks ({metadata_coverage:.1f}%)")

        # Sample metadata from first chunk
        if chunks_with_meta and chunks_with_meta[0].metadata.get("signature"):
            meta = chunks_with_meta[0].metadata
            print(f"   Sample complexity: cyclomatic={meta.get('complexity', {}).get('cyclomatic', 'N/A')}")
            print(f"   Sample params: {meta.get('parameters', [])}")
        print()

        results.append({
            "description": description,
            "num_functions": num_funcs,
            "lines": lines,
            "time_no_meta": time_no_meta,
            "time_with_meta": time_with_meta,
            "overhead_ms": overhead_ms,
            "overhead_pct": overhead_pct,
            "metadata_coverage": metadata_coverage
        })

    # Summary
    print("=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print()

    print(f"{'Benchmark':<40} {'Time (no meta)':<15} {'Time (with meta)':<15} {'Overhead':<15} {'Coverage'}")
    print("-" * 100)

    for r in results:
        print(f"{r['description']:<40} "
              f"{r['time_no_meta']:>10.2f}ms    "
              f"{r['time_with_meta']:>10.2f}ms    "
              f"+{r['overhead_ms']:>8.2f}ms    "
              f"{r['metadata_coverage']:>6.1f}%")

    print()

    # Performance targets check
    print("=" * 80)
    print("PERFORMANCE TARGETS VALIDATION")
    print("=" * 80)
    print()

    all_passed = True

    # Target 1: <50ms per 300 LOC
    target_300_loc = next((r for r in results if r['lines'] > 250 and r['lines'] < 1000), results[1])
    time_per_300_loc = (target_300_loc['time_with_meta'] / target_300_loc['lines']) * 300
    target_1_passed = time_per_300_loc < 50

    print(f"1. Target: <50ms for ~300 LOC with metadata")
    print(f"   Measured: {time_per_300_loc:.2f}ms for 300 LOC")
    print(f"   Status: {'✅ PASSED' if target_1_passed else '❌ FAILED'}")
    print()

    all_passed = all_passed and target_1_passed

    # Target 2: <5ms overhead per function
    avg_overhead_per_func = sum(r['overhead_ms'] / r['num_functions'] for r in results) / len(results)
    target_2_passed = avg_overhead_per_func < 5

    print(f"2. Target: <5ms metadata overhead per function")
    print(f"   Measured: {avg_overhead_per_func:.2f}ms per function")
    print(f"   Status: {'✅ PASSED' if target_2_passed else '❌ FAILED'}")
    print()

    all_passed = all_passed and target_2_passed

    # Target 3: >80% metadata coverage
    avg_coverage = sum(r['metadata_coverage'] for r in results) / len(results)
    target_3_passed = avg_coverage > 80

    print(f"3. Target: >80% metadata coverage")
    print(f"   Measured: {avg_coverage:.1f}% average coverage")
    print(f"   Status: {'✅ PASSED' if target_3_passed else '❌ FAILED'}")
    print()

    all_passed = all_passed and target_3_passed

    # Target 4: Linear scaling (overhead % should stay stable)
    overhead_variance = max(r['overhead_pct'] for r in results) - min(r['overhead_pct'] for r in results)
    target_4_passed = overhead_variance < 50  # Less than 50% variance

    print(f"4. Target: Linear scaling (stable overhead %)")
    print(f"   Measured: {overhead_variance:.1f}% variance")
    print(f"   Status: {'✅ PASSED' if target_4_passed else '❌ FAILED'}")
    print()

    all_passed = all_passed and target_4_passed

    if all_passed:
        print("🎉 ALL PERFORMANCE TARGETS MET!")
    else:
        print("⚠️ SOME PERFORMANCE TARGETS NOT MET")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(benchmark_performance())
    sys.exit(0 if success else 1)
