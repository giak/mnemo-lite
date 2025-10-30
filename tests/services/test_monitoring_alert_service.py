"""
Tests for EPIC-22 MonitoringAlertService.

EPIC-22: Tests smart alerting system via monitoring endpoints.
"""

import pytest


@pytest.mark.anyio
async def test_alerts_retrieval(test_client):
    """
    Test alert retrieval.

    EPIC-22: Validates fetching of unacknowledged alerts.
    """
    response = await test_client.get("/api/monitoring/advanced/alerts")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    for alert in result:
        assert "alert_type" in alert
        assert "severity" in alert
        assert "message" in alert
        assert "value" in alert
        assert "threshold" in alert


@pytest.mark.anyio
async def test_alert_counts_by_severity(test_client):
    """
    Test alert counts by severity.

    EPIC-22: Validates grouping of alerts by severity level.
    """
    response = await test_client.get("/api/monitoring/advanced/alerts/counts")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, dict)
    # Counts may be 0 if no alerts
    for severity in ["critical", "warning", "info"]:
        if severity in result:
            assert isinstance(result[severity], int)
            assert result[severity] >= 0
