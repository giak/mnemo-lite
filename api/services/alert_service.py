"""
Alert Service for monitoring error thresholds and triggering alerts.

Story: EPIC-12 Story 12.4 - Error Tracking & Alerting
Author: Claude Code
Date: 2025-10-22
"""

import asyncio
import structlog
from typing import Optional
from datetime import datetime

from services.error_tracking_service import ErrorTrackingService

# Get structured logger
logger = structlog.get_logger(__name__)


class AlertService:
    """
    Background service for checking error thresholds and triggering alerts.

    Runs periodically (every 5 minutes) to check error thresholds
    and log alerts when thresholds are exceeded.

    Future enhancements:
    - Email notifications
    - Slack/Discord webhooks
    - PagerDuty integration
    - Custom alert rules

    Attributes:
        error_tracking: Error tracking service for checking thresholds
        logger: Structured logger
        check_interval: Interval between checks in seconds (default: 300 = 5 min)
        _task: Background task reference
        _running: Flag indicating if service is running
    """

    def __init__(
        self,
        error_tracking_service: ErrorTrackingService,
        check_interval: int = 300  # 5 minutes
    ):
        """
        Initialize alert service.

        Args:
            error_tracking_service: Service for error tracking and threshold checks
            check_interval: Interval between checks in seconds (default: 300)
        """
        self.error_tracking = error_tracking_service
        self.check_interval = check_interval
        self.logger = structlog.get_logger(__name__)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """
        Start alert monitoring task.

        Creates background task that runs every `check_interval` seconds.
        """
        if self._running:
            self.logger.warning("AlertService already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.logger.info(
            "AlertService started",
            check_interval=self.check_interval
        )

    async def stop(self) -> None:
        """
        Stop alert monitoring task.

        Cancels background task and waits for cleanup.
        """
        if not self._running:
            self.logger.warning("AlertService not running")
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.logger.info("AlertService stopped")

    async def _monitor_loop(self) -> None:
        """
        Monitor errors and trigger alerts periodically.

        This loop runs continuously, checking thresholds every
        `check_interval` seconds and logging alerts when exceeded.
        """
        self.logger.info("Alert monitoring loop started")

        while self._running:
            try:
                # Wait for check interval
                await asyncio.sleep(self.check_interval)

                if not self._running:
                    break

                # Check thresholds
                alerts = await self.error_tracking.check_alert_thresholds()

                if alerts:
                    for alert in alerts:
                        self.logger.warning(
                            f"ALERT TRIGGERED: {alert}",
                            alert_type="threshold_exceeded",
                            timestamp=datetime.utcnow().isoformat()
                        )
                        # Future: Send email, Slack, webhook
                        await self._send_alert(alert)
                else:
                    self.logger.debug(
                        "Alert check completed, no thresholds exceeded",
                        timestamp=datetime.utcnow().isoformat()
                    )

            except asyncio.CancelledError:
                self.logger.info("Alert monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(
                    f"Error in alert monitoring loop: {e}",
                    exc_info=e
                )
                # Continue loop even if check fails

        self.logger.info("Alert monitoring loop stopped")

    async def _send_alert(self, message: str) -> None:
        """
        Send alert notification.

        Currently: Log only (alerts visible in structlog output)

        Future enhancements:
        - Email via SMTP
        - Slack webhook
        - Discord webhook
        - PagerDuty API
        - Custom webhook URL

        Args:
            message: Alert message to send

        Example future implementation:
            # Email
            if self.smtp_configured:
                await self._send_email_alert(message)

            # Slack
            if self.slack_webhook_url:
                await self._send_slack_alert(message)

            # Custom webhook
            if self.webhook_url:
                await self._send_webhook_alert(message)
        """
        # Placeholder for future notification integrations
        # For now, alerts are logged via structlog (see _monitor_loop)
        pass

    async def check_now(self) -> list[str]:
        """
        Check alert thresholds immediately (on-demand).

        Useful for testing or manual checks outside the monitoring loop.

        Returns:
            List of alert messages (empty if no thresholds exceeded)

        Example:
            alerts = await alert_service.check_now()
            if alerts:
                print("Current alerts:", alerts)
        """
        return await self.error_tracking.check_alert_thresholds()

    def is_running(self) -> bool:
        """
        Check if alert service is currently running.

        Returns:
            True if service is running, False otherwise
        """
        return self._running
