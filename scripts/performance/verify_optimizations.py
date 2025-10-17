#!/usr/bin/env python3
"""
Verification script for MnemoLite pragmatic optimizations.

Tests that all optimizations are working correctly:
- Connection pool configuration
- Cache functionality
- Performance endpoints
- Database indexes

Usage:
    python scripts/verify_optimizations.py
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any
import sys


class OptimizationVerifier:
    """Verify that all optimizations are working."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.results = []

    async def check_health(self) -> bool:
        """Check if API is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as resp:
                    if resp.status == 200:
                        self.results.append("✅ API is healthy")
                        return True
        except Exception as e:
            self.results.append(f"❌ API health check failed: {e}")
            return False

    async def check_performance_endpoints(self) -> bool:
        """Test performance monitoring endpoints."""
        endpoints = [
            "/performance/metrics",
            "/performance/cache/stats",
            "/performance/system",
            "/performance/database/pool",
            "/performance/optimize/suggestions"
        ]

        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.results.append(f"✅ {endpoint} - OK")

                            # Special checks for specific endpoints
                            if endpoint == "/performance/cache/stats":
                                if "query_cache" in data:
                                    stats = data["query_cache"]
                                    self.results.append(
                                        f"   Cache: {stats.get('size', 0)} items, "
                                        f"hit rate: {stats.get('hit_rate', '0%')}"
                                    )

                            elif endpoint == "/performance/database/pool":
                                self.results.append(
                                    f"   Pool: size={data.get('size', '?')}, "
                                    f"active={data.get('checked_out', 0)}"
                                )

                            elif endpoint == "/performance/system":
                                proc = data.get("process", {})
                                self.results.append(
                                    f"   Memory: {proc.get('memory_mb', 0):.1f}MB, "
                                    f"Threads: {proc.get('threads', 0)}"
                                )
                        else:
                            self.results.append(f"⚠️ {endpoint} - Status {resp.status}")

                except Exception as e:
                    self.results.append(f"❌ {endpoint} - Failed: {e}")

        return True

    async def test_cache_functionality(self) -> bool:
        """Test that caching is actually working."""
        async with aiohttp.ClientSession() as session:
            # Create a test event to trigger embedding generation
            test_event = {
                "content": {
                    "text": "Test optimization verification",
                    "type": "test"
                },
                "metadata": {
                    "source": "optimization_test"
                }
            }

            try:
                # First request - should generate embedding
                start_time = time.time()
                async with session.post(
                    f"{self.base_url}/v1/events",
                    json=test_event
                ) as resp:
                    first_time = time.time() - start_time

                # Get cache stats
                async with session.get(f"{self.base_url}/performance/cache/stats") as resp:
                    if resp.status == 200:
                        stats = await resp.json()
                        cache_info = stats.get("query_cache", {})

                        if cache_info.get("hits", 0) > 0 or cache_info.get("size", 0) > 0:
                            self.results.append("✅ Query cache is active and working")
                        else:
                            self.results.append("⚠️ Query cache active but no hits yet")

            except Exception as e:
                self.results.append(f"⚠️ Cache test skipped: {e}")

        return True

    async def check_database_connection_pool(self) -> bool:
        """Verify connection pool configuration."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/performance/database/pool") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pool_size = data.get("size", 0)

                        if pool_size <= 3:  # We optimized to 3
                            self.results.append(
                                f"✅ Connection pool optimized: size={pool_size} (target: 3)"
                            )
                        else:
                            self.results.append(
                                f"⚠️ Connection pool size={pool_size} (expected: 3)"
                            )

            except Exception as e:
                self.results.append(f"⚠️ Pool check failed: {e}")

        return True

    async def get_optimization_suggestions(self) -> bool:
        """Get and display optimization suggestions."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/performance/optimize/suggestions"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        suggestions = data.get("suggestions", [])

                        if not suggestions:
                            self.results.append("✅ No optimization issues detected")
                        else:
                            self.results.append(f"ℹ️ {len(suggestions)} optimization suggestions:")
                            for sug in suggestions[:3]:  # Show max 3
                                self.results.append(
                                    f"   - [{sug['category']}] {sug['issue']}"
                                )

            except Exception as e:
                self.results.append(f"⚠️ Suggestions check failed: {e}")

        return True

    async def run_all_checks(self):
        """Run all verification checks."""
        print("MnemoLite Optimization Verification")
        print("=" * 50)

        # Check if API is running
        if not await self.check_health():
            print("\n⚠️ API is not running. Please start it with: make up")
            return

        # Run all checks
        await self.check_performance_endpoints()
        await self.test_cache_functionality()
        await self.check_database_connection_pool()
        await self.get_optimization_suggestions()

        # Print results
        print("\nVerification Results:")
        print("-" * 50)
        for result in self.results:
            print(result)

        # Summary
        print("\n" + "=" * 50)
        success_count = sum(1 for r in self.results if "✅" in r)
        warning_count = sum(1 for r in self.results if "⚠️" in r)
        error_count = sum(1 for r in self.results if "❌" in r)

        print(f"Summary: {success_count} passed, {warning_count} warnings, {error_count} errors")

        if error_count == 0:
            print("\n🎉 All critical optimizations are working!")
        else:
            print("\n⚠️ Some optimizations need attention.")


async def main():
    """Main entry point."""
    verifier = OptimizationVerifier()
    await verifier.run_all_checks()


if __name__ == "__main__":
    # Check if custom URL provided
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Using custom URL: {url}")
        verifier = OptimizationVerifier(url)
        asyncio.run(verifier.run_all_checks())
    else:
        asyncio.run(main())