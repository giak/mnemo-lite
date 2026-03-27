"""add_memory_decay_config

Revision ID: e5a8b3c9d203
Revises: c4d7f2a8e102
Create Date: 2026-03-27 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5a8b3c9d203'
down_revision: Union[str, Sequence[str], None] = 'c4d7f2a8e102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add memory_decay_config table for tag-based decay and auto-consolidation.

    Replaces hardcoded DECAY_PRESETS with configurable per-tag rules.
    Supports auto-consolidation thresholds and priority boosts for search ranking.

    Presets (Expanse):
        sys:core      → rate=0.000 (permanent)
        sys:anchor    → rate=0.000 (permanent)
        sys:pattern   → rate=0.005 (~140 days half-life)
        sys:extension → rate=0.010 (~70 days)
        sys:history   → rate=0.050 (~14 days, auto-consolidate at 20)
        sys:drift     → rate=0.020 (~35 days, priority boost +0.3)
        TRACE:FRESH   → rate=0.100 (~7 days, priority boost +0.4)
    """

    op.execute("""
        CREATE TABLE memory_decay_config (
            tag_pattern VARCHAR(200) PRIMARY KEY,
            decay_rate DECIMAL(6,4) NOT NULL,
            half_life_days INTEGER,
            auto_consolidate_threshold INTEGER DEFAULT NULL,
            priority_boost DECIMAL(3,2) DEFAULT 0.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # Insert Expanse presets
    op.execute("""
        INSERT INTO memory_decay_config (tag_pattern, decay_rate, half_life_days, auto_consolidate_threshold, priority_boost) VALUES
        ('sys:core',      0.000, NULL, NULL,  0.50),
        ('sys:anchor',    0.000, NULL, NULL,  0.50),
        ('sys:pattern',   0.005, 139,  NULL,  0.20),
        ('sys:extension', 0.010, 69,   NULL,  0.00),
        ('sys:history',   0.050, 14,   20,   -0.10),
        ('sys:drift',     0.020, 35,   NULL,  0.30),
        ('TRACE:FRESH',   0.100, 7,    NULL,  0.40);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_decay_config;")
