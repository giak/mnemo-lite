#!/usr/bin/env python3
"""
Cache Performance Benchmark Script for EPIC-10

Tests:
1. L1/L2 cache hit rates
2. Search query performance (cached vs uncached)
3. Cache cascade performance (L2→L1 promotion)

Expected Results:
- Cache hit rate >90%
- Cached queries <10ms
- 10× speedup on repeated queries
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import sys
from pathlib import Path
import json

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import httpx
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx", "colorama"], check=True)
    import httpx
    from colorama import init, Fore, Style
    init(autoreset=True)


class CacheBenchmark:
    """Benchmark cache performance via API endpoints."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.results: Dict[str, Any] = {}

    async def check_health(self) -> bool:
        """Check if API is available."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            print(f"{Fore.RED}❌ API not available: {e}{Style.RESET_ALL}")
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/v1/cache/stats", timeout=5.0)
            response.raise_for_status()
            return response.json()

    async def flush_cache(self, scope: str = "all") -> None:
        """Flush cache for clean benchmark start."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/cache/flush",
                json={"scope": scope},
                timeout=10.0
            )
            response.raise_for_status()

    async def search_code(self, query: str, mode: str = "hybrid") -> Dict[str, Any]:
        """Execute code search query."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/code/search/{mode}",
                json={"query": query, "limit": 10},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def benchmark_search_latency(self, num_runs: int = 20) -> Dict[str, float]:
        """Benchmark search latency with and without cache."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 Benchmark 1: Search Latency (Cached vs Uncached){Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

        # Flush cache for clean start
        print(f"\n{Fore.YELLOW}🗑️  Flushing cache...{Style.RESET_ALL}")
        await self.flush_cache()
        await asyncio.sleep(1)  # Let cache settle

        # Test query
        query = "authentication"

        # COLD RUN - Cache miss
        print(f"\n{Fore.BLUE}❄️  Cold run (cache miss)...{Style.RESET_ALL}")
        cold_latencies = []
        for i in range(3):  # Only 3 cold runs (expensive)
            start = time.perf_counter()
            try:
                await self.search_code(query, mode="hybrid")
                latency_ms = (time.perf_counter() - start) * 1000
                cold_latencies.append(latency_ms)
                print(f"  Run {i+1}/3: {latency_ms:.1f}ms", end="\r")
            except Exception as e:
                print(f"\n{Fore.RED}  Error: {e}{Style.RESET_ALL}")

        cold_median = statistics.median(cold_latencies) if cold_latencies else 0
        print(f"\n{Fore.BLUE}  Cold median: {cold_median:.1f}ms{Style.RESET_ALL}")

        # HOT RUNS - Cache hits
        print(f"\n{Fore.GREEN}🔥 Hot runs (cache hits)...{Style.RESET_ALL}")
        hot_latencies = []
        for i in range(num_runs):
            start = time.perf_counter()
            try:
                await self.search_code(query, mode="hybrid")
                latency_ms = (time.perf_counter() - start) * 1000
                hot_latencies.append(latency_ms)
                print(f"  Run {i+1}/{num_runs}: {latency_ms:.1f}ms", end="\r")
            except Exception as e:
                print(f"\n{Fore.RED}  Error: {e}{Style.RESET_ALL}")

        if not hot_latencies:
            return {"error": "No successful hot runs"}

        hot_median = statistics.median(hot_latencies)
        hot_p95 = statistics.quantiles(hot_latencies, n=20)[18]  # 95th percentile
        hot_p99 = statistics.quantiles(hot_latencies, n=100)[98]  # 99th percentile

        speedup = cold_median / hot_median if hot_median > 0 else 0

        print(f"\n\n{Fore.GREEN}{'─'*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Results:{Style.RESET_ALL}")
        print(f"  Cold (no cache): {cold_median:.1f}ms")
        print(f"  Hot (cached):    {hot_median:.1f}ms (P50)")
        print(f"                   {hot_p95:.1f}ms (P95)")
        print(f"                   {hot_p99:.1f}ms (P99)")
        print(f"  {Fore.YELLOW}Speedup: {speedup:.1f}×{Style.RESET_ALL}")

        # Check acceptance criteria
        if speedup >= 10:
            print(f"  {Fore.GREEN}✅ PASS: Speedup >10× (target met!){Style.RESET_ALL}")
        elif speedup >= 5:
            print(f"  {Fore.YELLOW}⚠️  WARN: Speedup {speedup:.1f}× (target: >10×){Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}❌ FAIL: Speedup {speedup:.1f}× (target: >10×){Style.RESET_ALL}")

        if hot_median < 10:
            print(f"  {Fore.GREEN}✅ PASS: Cached latency <10ms{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}⚠️  WARN: Cached latency {hot_median:.1f}ms (target: <10ms){Style.RESET_ALL}")

        results = {
            "cold_median_ms": cold_median,
            "hot_median_ms": hot_median,
            "hot_p95_ms": hot_p95,
            "hot_p99_ms": hot_p99,
            "speedup": speedup,
            "pass": speedup >= 10 and hot_median < 10
        }

        self.results["search_latency"] = results
        return results

    async def benchmark_cache_hit_rate(self, num_queries: int = 100) -> Dict[str, Any]:
        """Benchmark cache hit rate over multiple queries."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 Benchmark 2: Cache Hit Rate{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

        # Get initial stats
        stats_before = await self.get_cache_stats()

        # Run varied queries (some repeated to test cache)
        queries = [
            "authentication", "authorization", "database", "cache", "search",
            "function", "class", "import", "export", "api"
        ]

        print(f"\n{Fore.BLUE}🔍 Running {num_queries} varied queries...{Style.RESET_ALL}")

        for i in range(num_queries):
            query = queries[i % len(queries)]  # Cycle through queries
            try:
                await self.search_code(query, mode="hybrid")
                print(f"  Query {i+1}/{num_queries}: '{query}'", end="\r")
            except Exception as e:
                print(f"\n{Fore.RED}  Error on query {i+1}: {e}{Style.RESET_ALL}")

        # Get final stats
        stats_after = await self.get_cache_stats()

        # Calculate hit rate
        l1_hit_rate = stats_after.get("l1_hit_rate", 0)
        l2_hit_rate = stats_after.get("l2_hit_rate", 0)
        combined_hit_rate = stats_after.get("combined_hit_rate", 0)

        print(f"\n\n{Fore.GREEN}{'─'*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Cache Statistics:{Style.RESET_ALL}")
        print(f"  L1 Hit Rate: {l1_hit_rate:.1f}%")
        print(f"  L2 Hit Rate: {l2_hit_rate:.1f}%")
        print(f"  {Fore.YELLOW}Combined Hit Rate: {combined_hit_rate:.1f}%{Style.RESET_ALL}")

        # Check acceptance criteria
        if combined_hit_rate >= 90:
            print(f"  {Fore.GREEN}✅ PASS: Hit rate ≥90% (target met!){Style.RESET_ALL}")
        elif combined_hit_rate >= 80:
            print(f"  {Fore.YELLOW}⚠️  WARN: Hit rate {combined_hit_rate:.1f}% (target: ≥90%){Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}❌ FAIL: Hit rate {combined_hit_rate:.1f}% (target: ≥90%){Style.RESET_ALL}")

        results = {
            "l1_hit_rate": l1_hit_rate,
            "l2_hit_rate": l2_hit_rate,
            "combined_hit_rate": combined_hit_rate,
            "num_queries": num_queries,
            "pass": combined_hit_rate >= 90
        }

        self.results["cache_hit_rate"] = results
        return results

    async def benchmark_cache_cascade(self, num_runs: int = 50) -> Dict[str, Any]:
        """Benchmark L2→L1 cascade performance."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 Benchmark 3: Cache Cascade (L2→L1 Promotion){Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

        # Flush L1 only, keep L2 populated
        print(f"\n{Fore.YELLOW}🗑️  Flushing L1 cache only...{Style.RESET_ALL}")
        await self.flush_cache(scope="l1")
        await asyncio.sleep(1)

        # Query should hit L2 and promote to L1
        query = "cascade_test"

        print(f"\n{Fore.BLUE}🔄 Testing L2→L1 promotion...{Style.RESET_ALL}")
        latencies = []

        for i in range(num_runs):
            start = time.perf_counter()
            try:
                await self.search_code(query, mode="hybrid")
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
                print(f"  Run {i+1}/{num_runs}: {latency_ms:.1f}ms", end="\r")
            except Exception as e:
                print(f"\n{Fore.RED}  Error: {e}{Style.RESET_ALL}")

        if not latencies:
            return {"error": "No successful runs"}

        median = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]

        # Get promotion stats
        stats = await self.get_cache_stats()
        promotions = stats.get("cascade", {}).get("l2_to_l1_promotions", 0)

        print(f"\n\n{Fore.GREEN}{'─'*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Cascade Performance:{Style.RESET_ALL}")
        print(f"  Median latency: {median:.1f}ms (P50)")
        print(f"  P95 latency:    {p95:.1f}ms")
        print(f"  L2→L1 promotions: {promotions}")

        if median < 20:  # L2 hits should be fast
            print(f"  {Fore.GREEN}✅ PASS: L2 cascade latency <20ms{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}⚠️  WARN: L2 cascade latency {median:.1f}ms{Style.RESET_ALL}")

        results = {
            "median_ms": median,
            "p95_ms": p95,
            "promotions": promotions,
            "pass": median < 20
        }

        self.results["cache_cascade"] = results
        return results

    def print_summary(self):
        """Print final summary report."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 EPIC-10 Cache Benchmark - Summary Report{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

        all_pass = True

        # Test 1: Search Latency
        if "search_latency" in self.results:
            r = self.results["search_latency"]
            status = "✅ PASS" if r.get("pass") else "❌ FAIL"
            print(f"1. {Fore.YELLOW}Search Latency:{Style.RESET_ALL} {status}")
            print(f"   - Speedup: {r.get('speedup', 0):.1f}× (target: >10×)")
            print(f"   - Cached latency: {r.get('hot_median_ms', 0):.1f}ms (target: <10ms)")
            all_pass &= r.get("pass", False)

        # Test 2: Cache Hit Rate
        if "cache_hit_rate" in self.results:
            r = self.results["cache_hit_rate"]
            status = "✅ PASS" if r.get("pass") else "❌ FAIL"
            print(f"\n2. {Fore.YELLOW}Cache Hit Rate:{Style.RESET_ALL} {status}")
            print(f"   - Combined: {r.get('combined_hit_rate', 0):.1f}% (target: ≥90%)")
            print(f"   - L1: {r.get('l1_hit_rate', 0):.1f}%")
            print(f"   - L2: {r.get('l2_hit_rate', 0):.1f}%")
            all_pass &= r.get("pass", False)

        # Test 3: Cache Cascade
        if "cache_cascade" in self.results:
            r = self.results["cache_cascade"]
            status = "✅ PASS" if r.get("pass") else "⚠️  OK"
            print(f"\n3. {Fore.YELLOW}Cache Cascade:{Style.RESET_ALL} {status}")
            print(f"   - L2 latency: {r.get('median_ms', 0):.1f}ms (target: <20ms)")
            print(f"   - Promotions: {r.get('promotions', 0)}")

        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

        if all_pass:
            print(f"{Fore.GREEN}✅ ALL TESTS PASSED - EPIC-10 Performance Targets Met!{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️  SOME TESTS FAILED - Review results above{Style.RESET_ALL}")

        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

        # Save results to JSON
        results_file = project_root / "scripts" / "benchmarks" / "cache_benchmark_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"📝 Results saved to: {results_file}")


async def main():
    """Run all cache benchmarks."""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🚀 EPIC-10 Cache Performance Benchmark{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    benchmark = CacheBenchmark()

    # Check API availability
    print(f"{Fore.BLUE}🔍 Checking API availability...{Style.RESET_ALL}")
    if not await benchmark.check_health():
        print(f"\n{Fore.RED}❌ API not available at http://localhost:8001{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Start the API with: make up{Style.RESET_ALL}\n")
        sys.exit(1)

    print(f"{Fore.GREEN}✅ API is ready{Style.RESET_ALL}\n")

    try:
        # Run all benchmarks
        await benchmark.benchmark_search_latency(num_runs=20)
        await benchmark.benchmark_cache_hit_rate(num_queries=100)
        await benchmark.benchmark_cache_cascade(num_runs=50)

        # Print summary
        benchmark.print_summary()

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}⚠️  Benchmark interrupted by user{Style.RESET_ALL}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Fore.RED}❌ Benchmark failed: {e}{Style.RESET_ALL}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
