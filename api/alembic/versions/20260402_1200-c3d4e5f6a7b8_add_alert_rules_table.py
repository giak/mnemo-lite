"""add_alert_rules_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-02 12:00:00.000000

EPIC-30 Story 30.1: Add alert_rules table for managing alert rules
from the UI. Previously alert thresholds were hardcoded.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create alert_rules table for UI-managed alert configuration."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
                'cache_hit_rate_low', 'memory_high', 'slow_queries',
                'error_rate_high', 'evictions_high', 'cpu_high',
                'disk_high', 'connections_high'
            )),
            threshold FLOAT NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'warning'
                CHECK (severity IN ('info', 'warning', 'critical')),
            cooldown_seconds INTEGER NOT NULL DEFAULT 300,
            enabled BOOLEAN NOT NULL DEFAULT true,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_rules_type
            ON alert_rules(alert_type)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled
            ON alert_rules(enabled)
    """)

    # Seed default rules matching current hardcoded thresholds
    op.execute("""
        INSERT INTO alert_rules (name, alert_type, threshold, severity, cooldown_seconds) VALUES
        ('Cache Hit Rate Low', 'cache_hit_rate_low', 0.8, 'warning', 300),
        ('Memory Usage High', 'memory_high', 0.85, 'critical', 600),
        ('Slow Queries Detected', 'slow_queries', 1.0, 'warning', 300),
        ('Error Rate High', 'error_rate_high', 0.05, 'critical', 300),
        ('Evictions High', 'evictions_high', 10.0, 'warning', 300),
        ('CPU Usage High', 'cpu_high', 0.8, 'warning', 300),
        ('Disk Usage High', 'disk_high', 0.9, 'critical', 600),
        ('Connections High', 'connections_high', 0.8, 'warning', 300)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_alert_rules_enabled")
    op.execute("DROP INDEX IF EXISTS idx_alert_rules_type")
    op.execute("DROP TABLE IF EXISTS alert_rules")
