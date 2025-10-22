"""
Tests for error tracking service.

Story: EPIC-12 Story 12.4 - Error Tracking & Alerting
Author: Claude Code
Date: 2025-10-22
"""

import pytest
from db.repositories.error_repository import ErrorRepository
from services.error_tracking_service import (
    ErrorTrackingService,
    ErrorSeverity,
    ErrorCategory
)


@pytest.mark.anyio
async def test_error_repository_create_error(test_engine):
    """Test creating an error log entry."""
    repo = ErrorRepository(test_engine)

    error_id = await repo.create_error(
        severity="ERROR",
        category="database",
        service="TestService",
        error_type="ValueError",
        message="Test error message",
        stack_trace="Traceback...",
        context={"request_id": "123"}
    )

    assert error_id is not None


@pytest.mark.anyio
async def test_error_tracking_service_log_error(test_engine):
    """Test logging an error through the service."""
    repo = ErrorRepository(test_engine)
    service = ErrorTrackingService(repo)

    try:
        raise ValueError("Test error")
    except ValueError as e:
        await service.log_error(
            error=e,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.API,
            service="TestService",
            context={"request_id": "456"}
        )

    # Give fire-and-forget task time to complete
    import asyncio
    await asyncio.sleep(0.5)

    # Verify error was logged
    summary = await service.get_error_summary(hours=1)
    assert len(summary) > 0
    assert any(s['error_type'] == 'ValueError' for s in summary)


@pytest.mark.anyio
async def test_error_summary(test_engine):
    """Test getting error summary."""
    repo = ErrorRepository(test_engine)

    # Create multiple errors
    for i in range(5):
        await repo.create_error(
            severity="ERROR",
            category="api",
            service="TestService",
            error_type="TestError",
            message=f"Error {i}",
            context={}
        )

    summary = await repo.get_error_summary(hours=24)
    assert len(summary) > 0

    # Find our test errors
    test_errors = [s for s in summary if s['error_type'] == 'TestError']
    assert len(test_errors) > 0
    assert test_errors[0]['total_count'] >= 5


@pytest.mark.anyio
async def test_critical_errors(test_engine):
    """Test getting critical errors."""
    repo = ErrorRepository(test_engine)

    # Create critical error
    await repo.create_error(
        severity="CRITICAL",
        category="database",
        service="TestService",
        error_type="CriticalError",
        message="Critical failure",
        context={}
    )

    critical = await repo.get_critical_errors(hours=1)
    assert any(e['error_type'] == 'CriticalError' for e in critical)


@pytest.mark.anyio
async def test_alert_thresholds(test_engine):
    """Test alert threshold checking."""
    repo = ErrorRepository(test_engine)
    service = ErrorTrackingService(repo)

    # Create enough errors to trigger threshold
    for i in range(12):
        await repo.create_error(
            severity="ERROR",
            category="api",
            service="TestService",
            error_type="ThresholdError",
            message=f"Error {i}",
            context={}
        )

    alerts = await service.check_alert_thresholds()
    # Should have alert for >10 errors in 1 hour
    assert any("ERROR" in alert for alert in alerts)


@pytest.mark.anyio
async def test_error_stats(test_engine):
    """Test getting comprehensive error stats."""
    repo = ErrorRepository(test_engine)
    service = ErrorTrackingService(repo)

    # Create various errors
    await repo.create_error(
        severity="ERROR",
        category="api",
        service="TestService",
        error_type="StatError",
        message="Stat test",
        context={}
    )

    stats = await service.get_error_stats()
    assert 'total_errors_24h' in stats
    assert 'critical_errors_1h' in stats
    assert 'top_error_types' in stats
    assert 'alerts' in stats
