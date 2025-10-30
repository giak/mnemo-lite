"""
Tests for EPIC-22 MetricsCollector Service.

EPIC-22: These tests validate metrics collection via the /summary endpoint.
The endpoint internally uses MetricsCollector.collect_all().
"""

import pytest


@pytest.mark.anyio
async def test_metrics_collector_via_endpoint(test_client):
    """
    Test MetricsCollector via /summary endpoint.

    EPIC-22: Validates collector.collect_all() returns all metric categories.
    """
    response = await test_client.get("/api/monitoring/advanced/summary")

    assert response.status_code == 200
    result = response.json()

    # Verify all metric categories exist (MetricsCollector.collect_all())
    assert "api" in result
    assert "redis" in result
    assert "postgres" in result
    assert "system" in result

    # Verify API metrics structure
    assert "request_count" in result["api"]
    assert "avg_latency_ms" in result["api"]
    assert "p50_latency_ms" in result["api"]
    assert "p95_latency_ms" in result["api"]
    assert "p99_latency_ms" in result["api"]
    assert "error_count" in result["api"]

    # Verify Redis metrics structure
    assert "connected" in result["redis"]
    assert "memory_used_mb" in result["redis"]
    assert "hit_rate" in result["redis"]

    # Verify PostgreSQL metrics structure
    assert "connections_total" in result["postgres"]
    assert "cache_hit_ratio" in result["postgres"]

    # Verify System metrics structure
    assert "cpu_percent" in result["system"]
    assert "memory_percent" in result["system"]


@pytest.mark.anyio
async def test_metrics_collector_with_custom_period(test_client):
    """
    Test MetricsCollector with custom period_hours parameter.

    EPIC-22: Validates period filtering in API metrics.
    """
    # Test default period (1 hour)
    response_1h = await test_client.get("/api/monitoring/advanced/summary?period_hours=1")
    assert response_1h.status_code == 200
    result_1h = response_1h.json()

    # Test extended period (24 hours)
    response_24h = await test_client.get("/api/monitoring/advanced/summary?period_hours=24")
    assert response_24h.status_code == 200
    result_24h = response_24h.json()

    # Both should have same structure
    for result in [result_1h, result_24h]:
        assert "api" in result
        assert "redis" in result
        assert "postgres" in result
        assert "system" in result
