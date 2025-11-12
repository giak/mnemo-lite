"""
EPIC-22 Story 22.7: Monitoring Alert Service

Smart alerting system that checks thresholds and creates alerts in database.

Thresholds:
- Cache hit rate < 70% → Warning
- Memory > 80% → Critical
- Slow queries > 10 (count) → Warning
- Evictions > 100/h → Info
- Error rate > 5% → Critical
- CPU > 90% → Warning
- Disk > 90% → Warning
- Connections > 80% → Warning

Author: Claude Code
Date: 2025-10-24
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class MonitoringAlertService:
    """
    Service for checking monitoring thresholds and creating alerts.

    Checks metrics from MetricsCollector and creates alerts in `alerts` table
    when thresholds are exceeded. Prevents duplicate alerts by checking
    if similar alert already exists and is unacknowledged.
    """

    def __init__(self, engine: AsyncEngine):
        """
        Initialize monitoring alert service.

        Args:
            engine: SQLAlchemy async engine for database access
        """
        self.engine = engine

        # Alert thresholds configuration
        self.thresholds = {
            'cache_hit_rate_low': {
                'threshold': 70.0,
                'severity': 'warning',
                'compare': 'lt',  # less than
                'message_template': 'Redis cache hit rate is {value:.1f}% (threshold: {threshold}%)'
            },
            'memory_high': {
                'threshold': 80.0,
                'severity': 'critical',
                'compare': 'gt',  # greater than
                'message_template': 'System memory usage is {value:.1f}% (threshold: {threshold}%)'
            },
            'slow_queries': {
                'threshold': 10,
                'severity': 'warning',
                'compare': 'gt',
                'message_template': '{value} slow queries detected (threshold: {threshold})'
            },
            'evictions_high': {
                'threshold': 100,  # per hour
                'severity': 'info',
                'compare': 'gt',
                'message_template': '{value} Redis evictions in last hour (threshold: {threshold})'
            },
            'error_rate_high': {
                'threshold': 5.0,  # percentage
                'severity': 'critical',
                'compare': 'gt',
                'message_template': 'API error rate is {value:.1f}% (threshold: {threshold}%)'
            },
            'cpu_high': {
                'threshold': 90.0,
                'severity': 'warning',
                'compare': 'gt',
                'message_template': 'CPU usage is {value:.1f}% (threshold: {threshold}%)'
            },
            'disk_high': {
                'threshold': 90.0,
                'severity': 'warning',
                'compare': 'gt',
                'message_template': 'Disk usage is {value:.1f}% (threshold: {threshold}%)'
            },
            'connections_high': {
                'threshold': 80.0,  # percentage of max connections
                'severity': 'warning',
                'compare': 'gt',
                'message_template': 'Database connections at {value:.1f}% (threshold: {threshold}%)'
            }
        }

    async def check_thresholds(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check all thresholds against current metrics.

        Args:
            metrics: Current metrics from MetricsCollector (format: {api, redis, postgres, system})

        Returns:
            List of alerts that were created (empty if no thresholds exceeded)

        Example metrics format:
            {
                'api': {'error_rate': 7.5, ...},
                'redis': {'hit_rate': 65.0, 'evicted_keys': 150, ...},
                'postgres': {'slow_queries_count': 15, 'connections_total': 85, 'connections_max': 100, ...},
                'system': {'memory_percent': 85.0, 'cpu_percent': 92.0, 'disk_percent': 88.0, ...}
            }
        """
        alerts_created = []

        # Extract relevant metric values
        checks = [
            ('cache_hit_rate_low', metrics.get('redis', {}).get('hit_rate', 100.0)),
            ('memory_high', metrics.get('system', {}).get('memory_percent', 0.0)),
            ('slow_queries', metrics.get('postgres', {}).get('slow_queries_count', 0)),
            ('evictions_high', await self._get_evictions_per_hour()),
            ('error_rate_high', metrics.get('api', {}).get('error_rate', 0.0)),
            ('cpu_high', metrics.get('system', {}).get('cpu_percent', 0.0)),
            ('disk_high', metrics.get('system', {}).get('disk_percent', 0.0)),
            ('connections_high', self._calculate_connections_percentage(metrics.get('postgres', {})))
        ]

        for alert_type, value in checks:
            if await self._should_create_alert(alert_type, value):
                alert = await self._create_alert(alert_type, value)
                if alert:
                    alerts_created.append(alert)
                    logger.warning(
                        "Alert created",
                        alert_type=alert_type,
                        severity=alert['severity'],
                        value=value,
                        threshold=alert['threshold']
                    )

        if not alerts_created:
            logger.debug("Threshold check completed, no alerts created")

        return alerts_created

    async def _should_create_alert(self, alert_type: str, value: float) -> bool:
        """
        Check if alert should be created based on threshold and existing alerts.

        Args:
            alert_type: Type of alert (e.g., 'cache_hit_rate_low')
            value: Current metric value

        Returns:
            True if alert should be created, False otherwise
        """
        config = self.thresholds.get(alert_type)
        if not config:
            return False

        threshold = config['threshold']
        compare = config['compare']

        # Check if threshold is exceeded
        threshold_exceeded = (
            (compare == 'gt' and value > threshold) or
            (compare == 'lt' and value < threshold)
        )

        if not threshold_exceeded:
            return False

        # Check if similar unacknowledged alert already exists (prevent duplicates)
        # Only create new alert if no unacknowledged alert exists for this type in last 1 hour
        existing_alert = await self._get_recent_unacknowledged_alert(alert_type, hours=1)
        if existing_alert:
            logger.debug(
                "Skipping alert creation, recent unacknowledged alert exists",
                alert_type=alert_type,
                existing_alert_id=existing_alert
            )
            return False

        return True

    async def _create_alert(self, alert_type: str, value: float) -> Optional[Dict[str, Any]]:
        """
        Create alert in database.

        Args:
            alert_type: Type of alert
            value: Current metric value

        Returns:
            Alert dictionary if created, None if failed
        """
        config = self.thresholds.get(alert_type)
        if not config:
            return None

        threshold = config['threshold']
        severity = config['severity']
        message = config['message_template'].format(
            value=value,
            threshold=threshold
        )

        try:
            async with self.engine.begin() as conn:
                query = text("""
                    INSERT INTO alerts (alert_type, severity, message, value, threshold, metadata)
                    VALUES (:alert_type, :severity, :message, :value, :threshold, CAST(:metadata AS jsonb))
                    RETURNING id, created_at, alert_type, severity, message, value, threshold
                """)

                result = await conn.execute(query, {
                    'alert_type': alert_type,
                    'severity': severity,
                    'message': message,
                    'value': value,
                    'threshold': threshold,
                    'metadata': '{}'  # Can add metadata later if needed
                })

                row = result.fetchone()
                if row:
                    return {
                        'id': str(row.id),
                        'created_at': row.created_at.isoformat(),
                        'alert_type': row.alert_type,
                        'severity': row.severity,
                        'message': row.message,
                        'value': row.value,
                        'threshold': row.threshold
                    }

        except Exception as e:
            logger.error("Failed to create alert", alert_type=alert_type, error=str(e))
            return None

    async def _get_recent_unacknowledged_alert(self, alert_type: str, hours: int = 1) -> Optional[str]:
        """
        Check if unacknowledged alert of same type exists in recent time window.

        Args:
            alert_type: Type of alert to check
            hours: Time window in hours (default: 1)

        Returns:
            Alert ID if exists, None otherwise
        """
        try:
            async with self.engine.begin() as conn:
                query = text("""
                    SELECT id
                    FROM alerts
                    WHERE alert_type = :alert_type
                      AND acknowledged = FALSE
                      AND created_at > NOW() - make_interval(hours => :hours)
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                result = await conn.execute(query, {
                    'alert_type': alert_type,
                    'hours': hours
                })

                row = result.fetchone()
                return str(row.id) if row else None

        except Exception as e:
            logger.error("Failed to check recent alerts", error=str(e))
            return None

    async def _get_evictions_per_hour(self) -> int:
        """
        Calculate Redis evictions in last hour from metrics table.

        Returns:
            Number of evictions in last hour
        """
        try:
            async with self.engine.begin() as conn:
                query = text("""
                    SELECT COUNT(*) as eviction_count
                    FROM metrics
                    WHERE metric_type = 'redis'
                      AND metric_name = 'evicted_keys'
                      AND timestamp > NOW() - INTERVAL '1 hour'
                      AND value > 0
                """)

                result = await conn.execute(query)
                row = result.fetchone()
                return int(row.eviction_count) if row else 0

        except Exception as e:
            logger.error("Failed to calculate evictions per hour", error=str(e))
            return 0

    def _calculate_connections_percentage(self, postgres_metrics: Dict[str, Any]) -> float:
        """
        Calculate percentage of database connections used.

        Args:
            postgres_metrics: PostgreSQL metrics dict

        Returns:
            Percentage of connections used (0-100)
        """
        total = postgres_metrics.get('connections_total', 0)
        max_conns = postgres_metrics.get('connections_max', 100)

        if max_conns == 0:
            return 0.0

        return (total / max_conns) * 100.0

    async def get_active_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all unacknowledged alerts.

        Args:
            limit: Maximum number of alerts to return (default: 100)

        Returns:
            List of alert dictionaries (newest first)
        """
        try:
            async with self.engine.begin() as conn:
                query = text("""
                    SELECT id, created_at, alert_type, severity, message, value, threshold, metadata
                    FROM alerts
                    WHERE acknowledged = FALSE
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)

                result = await conn.execute(query, {'limit': limit})
                rows = result.fetchall()

                return [
                    {
                        'id': str(row.id),
                        'created_at': row.created_at.isoformat(),
                        'alert_type': row.alert_type,
                        'severity': row.severity,
                        'message': row.message,
                        'value': row.value,
                        'threshold': row.threshold,
                        'metadata': row.metadata
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error("Failed to get active alerts", error=str(e))
            return []

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: UUID of alert to acknowledge
            acknowledged_by: User/system acknowledging (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.engine.begin() as conn:
                query = text("""
                    UPDATE alerts
                    SET acknowledged = TRUE,
                        acknowledged_at = NOW(),
                        acknowledged_by = :acknowledged_by
                    WHERE id = CAST(:alert_id AS uuid)
                      AND acknowledged = FALSE
                    RETURNING id
                """)

                result = await conn.execute(query, {
                    'alert_id': alert_id,
                    'acknowledged_by': acknowledged_by or 'system'
                })

                row = result.fetchone()
                success = row is not None

                if success:
                    logger.info("Alert acknowledged", alert_id=alert_id, acknowledged_by=acknowledged_by)

                return success

        except Exception as e:
            logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
            return False

    async def get_alert_counts(self) -> Dict[str, int]:
        """
        Get count of unacknowledged alerts by severity.

        Returns:
            Dict with counts: {'critical': 2, 'warning': 5, 'info': 1, 'total': 8}
        """
        try:
            async with self.engine.begin() as conn:
                query = text("""
                    SELECT
                        severity,
                        COUNT(*) as count
                    FROM alerts
                    WHERE acknowledged = FALSE
                    GROUP BY severity
                """)

                result = await conn.execute(query)
                rows = result.fetchall()

                counts = {'critical': 0, 'warning': 0, 'info': 0, 'total': 0}
                for row in rows:
                    counts[row.severity] = int(row.count)
                    counts['total'] += int(row.count)

                return counts

        except Exception as e:
            logger.error("Failed to get alert counts", error=str(e))
            return {'critical': 0, 'warning': 0, 'info': 0, 'total': 0}
