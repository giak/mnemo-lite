#!/usr/bin/env python3
"""
Test de Charge Progressive pour Embeddings - EPIC-18 (Version Simplifiée)

Test de performance avec montée en charge progressive pour valider
la stabilité et les performances de la génération d'embeddings.

Phases de test:
- Phase 1: 10 queries (warmup)
- Phase 2: 50 queries (charge légère)
- Phase 3: 100 queries (charge moyenne)
- Phase 4: 500 queries (charge élevée)
- Phase 5: 1000 queries (charge extrême)

Métriques mesurées:
- Latence (P50, P95, P99, max)
- Throughput (queries/sec)
- Taux de succès
- Utilisation mémoire
"""

import asyncio
import time
import statistics
import psutil

import sys
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, '/app')

from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from api.core import get_settings


# Test queries variées pour éviter le cache
TEST_QUERIES = [
    "validate email address format",
    "check user authentication",
    "parse JSON configuration",
    "sanitize SQL query input",
    "format string output",
    "detect security vulnerability",
    "calculate hash checksum",
    "compress file data",
    "encrypt sensitive information",
    "decode base64 encoding",
    "validate phone number",
    "check password strength",
    "parse XML document",
    "serialize object to JSON",
    "deserialize data structure",
    "validate credit card number",
    "check email domain MX record",
    "generate random token",
    "hash password with salt",
    "verify JWT signature",
    "parse URL parameters",
    "sanitize HTML content",
    "detect XSS attack",
    "prevent CSRF vulnerability",
    "rate limit API requests",
    "cache expensive operation",
    "retry failed network request",
    "handle connection timeout",
    "parse command line arguments",
    "validate input data type",
]


class LoadTestMetrics:
    """Collecte et analyse les métriques de charge."""

    def __init__(self, phase_name: str):
        self.phase_name = phase_name
        self.latencies: List[float] = []
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self.memory_start: float = 0
        self.memory_end: float = 0

    def start(self):
        """Démarre la collecte de métriques."""
        self.start_time = time.time()
        process = psutil.Process()
        self.memory_start = process.memory_info().rss / (1024 * 1024)  # MB

    def record_latency(self, latency_ms: float):
        """Enregistre une latence."""
        self.latencies.append(latency_ms)

    def record_error(self, error: str):
        """Enregistre une erreur."""
        self.errors.append(error)

    def finish(self):
        """Termine la collecte de métriques."""
        self.end_time = time.time()
        process = psutil.Process()
        self.memory_end = process.memory_info().rss / (1024 * 1024)  # MB

    def get_report(self) -> Dict[str, Any]:
        """Génère un rapport de métriques."""
        duration = self.end_time - self.start_time
        total_requests = len(self.latencies) + len(self.errors)

        if not self.latencies:
            return {
                "phase": self.phase_name,
                "total_requests": total_requests,
                "success_rate": 0.0,
                "errors": len(self.errors),
                "duration_sec": duration,
            }

        sorted_latencies = sorted(self.latencies)

        return {
            "phase": self.phase_name,
            "total_requests": total_requests,
            "successful": len(self.latencies),
            "errors": len(self.errors),
            "success_rate": (len(self.latencies) / total_requests * 100) if total_requests > 0 else 0,
            "duration_sec": round(duration, 2),
            "throughput_qps": round(total_requests / duration, 2) if duration > 0 else 0,
            "latency_p50_ms": round(sorted_latencies[len(sorted_latencies) // 2], 2),
            "latency_p95_ms": round(sorted_latencies[int(len(sorted_latencies) * 0.95)], 2),
            "latency_p99_ms": round(sorted_latencies[int(len(sorted_latencies) * 0.99)], 2),
            "latency_max_ms": round(max(sorted_latencies), 2),
            "latency_min_ms": round(min(sorted_latencies), 2),
            "latency_avg_ms": round(statistics.mean(sorted_latencies), 2),
            "memory_start_mb": round(self.memory_start, 1),
            "memory_end_mb": round(self.memory_end, 1),
            "memory_delta_mb": round(self.memory_end - self.memory_start, 1),
        }


async def test_embedding_generation(service: DualEmbeddingService, query: str, domain: EmbeddingDomain) -> float:
    """
    Test la génération d'un embedding et retourne la latence en ms.

    Returns:
        Latence en millisecondes
    """
    start = time.time()
    await service.generate_embedding(query, domain)
    elapsed = (time.time() - start) * 1000
    return elapsed


async def run_load_test_phase(
    phase_name: str,
    num_queries: int,
    embedding_service: DualEmbeddingService,
    domain: EmbeddingDomain
) -> LoadTestMetrics:
    """
    Exécute une phase de test de charge.

    Args:
        phase_name: Nom de la phase (e.g., "Phase 1: 10 queries")
        num_queries: Nombre de queries à tester
        embedding_service: Service d'embedding
        domain: Domaine d'embedding (TEXT ou CODE)

    Returns:
        Métriques de la phase
    """
    print(f"\n{'='*80}")
    print(f"🔥 {phase_name} - {num_queries} queries")
    print(f"{'='*80}")

    metrics = LoadTestMetrics(phase_name)
    metrics.start()

    # Générer les queries (cyclique si pas assez)
    queries = [TEST_QUERIES[i % len(TEST_QUERIES)] for i in range(num_queries)]

    # Exécuter les tests
    for i, query in enumerate(queries, 1):
        try:
            latency = await test_embedding_generation(embedding_service, query, domain)
            metrics.record_latency(latency)

            # Progress indicator
            if i % 10 == 0 or i == num_queries:
                print(f"  Progress: {i}/{num_queries} queries ({i/num_queries*100:.1f}%) - Last: {latency:.2f}ms")

        except Exception as e:
            metrics.record_error(str(e))
            print(f"  ❌ Error on query {i}: {e}")

    metrics.finish()

    return metrics


def print_ascii_chart(values: List[float], max_width: int = 50) -> None:
    """Affiche un graphique ASCII simple."""
    if not values:
        return

    max_val = max(values)
    min_val = min(values)
    range_val = max_val - min_val

    if range_val == 0:
        range_val = 1  # Éviter division par zéro

    for i, val in enumerate(values, 1):
        normalized = (val - min_val) / range_val
        bar_length = int(normalized * max_width)
        bar = '█' * bar_length
        print(f"  Phase {i}: {bar} {val:.2f}ms")


def print_report(metrics_list: List[LoadTestMetrics]) -> None:
    """Affiche un rapport détaillé."""
    print(f"\n{'='*80}")
    print("📊 RAPPORT DE TEST DE CHARGE PROGRESSIVE")
    print(f"{'='*80}")

    reports = [m.get_report() for m in metrics_list]

    # Tableau récapitulatif
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ RÉSUMÉ PAR PHASE                                                            │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")
    print(f"{'Phase':<20} {'Reqs':<8} {'Success':<10} {'Tput (q/s)':<12} {'P50':<10} {'P95':<10} {'P99':<10}")
    print("-" * 80)

    for report in reports:
        print(f"{report['phase']:<20} "
              f"{report['total_requests']:<8} "
              f"{report.get('success_rate', 0):<9.1f}% "
              f"{report.get('throughput_qps', 0):<11.2f} "
              f"{report.get('latency_p50_ms', 0):<9.2f}ms "
              f"{report.get('latency_p95_ms', 0):<9.2f}ms "
              f"{report.get('latency_p99_ms', 0):<9.2f}ms")

    # Métriques détaillées
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ LATENCE PAR PHASE                                                           │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")

    p50_values = [r.get('latency_p50_ms', 0) for r in reports if 'latency_p50_ms' in r]
    if p50_values:
        print("\nP50 Latency (médiane):")
        print_ascii_chart(p50_values)

    p95_values = [r.get('latency_p95_ms', 0) for r in reports if 'latency_p95_ms' in r]
    if p95_values:
        print("\nP95 Latency:")
        print_ascii_chart(p95_values)

    p99_values = [r.get('latency_p99_ms', 0) for r in reports if 'latency_p99_ms' in r]
    if p99_values:
        print("\nP99 Latency:")
        print_ascii_chart(p99_values)

    # Utilisation mémoire
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ UTILISATION MÉMOIRE                                                         │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")

    for report in reports:
        print(f"{report['phase']:<20} Start: {report.get('memory_start_mb', 0):.1f}MB | "
              f"End: {report.get('memory_end_mb', 0):.1f}MB | "
              f"Delta: {report.get('memory_delta_mb', 0):+.1f}MB")

    # Analyse globale
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ ANALYSE GLOBALE                                                             │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")

    total_requests = sum(r['total_requests'] for r in reports)
    total_errors = sum(r.get('errors', 0) for r in reports)
    avg_success_rate = statistics.mean([r.get('success_rate', 0) for r in reports if 'success_rate' in r])
    total_duration = sum(r.get('duration_sec', 0) for r in reports)

    print(f"\nTotal Requests: {total_requests}")
    print(f"Total Errors: {total_errors}")
    print(f"Average Success Rate: {avg_success_rate:.2f}%")
    print(f"Total Duration: {total_duration:.2f}s")

    if p50_values:
        print(f"\nLatency Evolution (P50):")
        print(f"  Start: {p50_values[0]:.2f}ms")
        print(f"  End: {p50_values[-1]:.2f}ms")
        change_pct = (p50_values[-1] - p50_values[0]) / p50_values[0] * 100 if p50_values[0] > 0 else 0
        print(f"  Change: {change_pct:+.1f}%")

    if p99_values:
        print(f"\nLatency Evolution (P99):")
        print(f"  Start: {p99_values[0]:.2f}ms")
        print(f"  End: {p99_values[-1]:.2f}ms")
        change_pct = (p99_values[-1] - p99_values[0]) / p99_values[0] * 100 if p99_values[0] > 0 else 0
        print(f"  Change: {change_pct:+.1f}%")

    # Recommandations
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ RECOMMANDATIONS                                                             │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")

    if p95_values and p95_values[-1] > 200:
        print("⚠️  Latence P95 élevée (>200ms) à forte charge → Considérer cache ou batching")
    elif p95_values and p95_values[-1] < 50:
        print("✅ Latence P95 excellente (<50ms)")

    if avg_success_rate < 95:
        print("⚠️  Taux de succès <95% → Vérifier logs d'erreurs")
    else:
        print("✅ Taux de succès excellent (>95%)")

    if reports and reports[-1].get('memory_delta_mb', 0) > 100:
        print("⚠️  Augmentation mémoire >100MB → Vérifier memory leaks")
    else:
        print("✅ Utilisation mémoire stable")

    if p50_values:
        change_pct = (p50_values[-1] - p50_values[0]) / p50_values[0] * 100 if p50_values[0] > 0 else 0
        if change_pct > 50:
            print(f"⚠️  Dégradation latence P50: {change_pct:+.1f}% → Vérifier scaling")
        else:
            print(f"✅ Latence stable (P50 change: {change_pct:+.1f}%)")


async def main():
    """Point d'entrée principal."""
    print("="*80)
    print("🚀 TEST DE CHARGE PROGRESSIVE - EMBEDDINGS (EPIC-18)")
    print("="*80)

    # Configuration
    embedding_mode = get_settings().EMBEDDING_MODE
    print(f"\n📋 Configuration:")
    print(f"  Mode: {embedding_mode}")
    print(f"  Domain: TEXT (queries)")

    # Service
    print("\n🔧 Initialisation du service d'embeddings...")
    embedding_service = DualEmbeddingService()

    # Phases de test
    phases = [
        ("Phase 1 (Warmup)", 10),
        ("Phase 2 (Light)", 50),
        ("Phase 3 (Medium)", 100),
        ("Phase 4 (Heavy)", 500),
        ("Phase 5 (Extreme)", 1000),
    ]

    print(f"\n📊 Phases de test: {len(phases)}")
    for name, count in phases:
        print(f"  - {name}: {count} queries")

    metrics_list = []

    for phase_name, num_queries in phases:
        metrics = await run_load_test_phase(
            phase_name=phase_name,
            num_queries=num_queries,
            embedding_service=embedding_service,
            domain=EmbeddingDomain.TEXT
        )
        metrics_list.append(metrics)

        # Afficher rapport de phase
        report = metrics.get_report()
        print(f"\n  ✅ Phase terminée:")
        print(f"     Duration: {report['duration_sec']}s")
        print(f"     Throughput: {report.get('throughput_qps', 0):.2f} q/s")
        print(f"     P50: {report.get('latency_p50_ms', 0):.2f}ms")
        print(f"     P95: {report.get('latency_p95_ms', 0):.2f}ms")

        # Pause entre phases
        await asyncio.sleep(1)

    # Rapport final
    print_report(metrics_list)

    print("\n✅ Test de charge terminé!")


if __name__ == "__main__":
    asyncio.run(main())
