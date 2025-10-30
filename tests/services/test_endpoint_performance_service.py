"""
Tests for EPIC-22 EndpointPerformanceService.

EPIC-22: Tests performance analysis by endpoint via monitoring endpoints.
"""

import pytest


@pytest.mark.anyio
async def test_endpoint_stats_via_endpoint(test_client):
    """
    Test endpoint stats aggregation.

    EPIC-22: Validates performance stats grouped by endpoint.
    """
    response = await test_client.get("/api/monitoring/advanced/performance/endpoints")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    # May be empty if no metrics recorded
    for endpoint_stat in result:
        assert "endpoint" in endpoint_stat
        assert "request_count" in endpoint_stat
        assert "avg_latency_ms" in endpoint_stat
        assert "p95_latency_ms" in endpoint_stat


@pytest.mark.anyio
async def test_slow_endpoints_detection(test_client):
    """
    Test slow endpoint detection.

    EPIC-22: Validates detection of endpoints exceeding latency threshold.
    """
    response = await test_client.get("/api/monitoring/advanced/performance/slow-endpoints?threshold_ms=100")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    for slow_endpoint in result:
        assert "endpoint" in slow_endpoint
        assert "impact_seconds_wasted_per_hour" in slow_endpoint
        assert "latency_above_target_ms" in slow_endpoint


@pytest.mark.anyio
async def test_error_hotspots_analysis(test_client):
    """
    Test error hotspot analysis.

    EPIC-22: Validates error breakdown by endpoint and status code.
    """
    response = await test_client.get("/api/monitoring/advanced/performance/error-hotspots")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    for hotspot in result:
        assert "endpoint" in hotspot
        assert "status_codes" in hotspot
        assert "total_errors" in hotspot
