"""add_protocol_trace_decay_presets

Revision ID: f1a2b3c4d506
Revises: e5a8b3c9d203
Create Date: 2026-04-01 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f1a2b3c4d506'
down_revision: Union[str, Sequence[str], None] = 'e5a8b3c9d203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add sys:protocol and sys:trace to memory_decay_config.

    Taxonomy completion to 11 tags:
        sys:protocol  → rate=0.002 (~1 year, operational rules, priority boost +0.30)
        sys:trace     → rate=0.080 (~9 days, agent execution traces, priority boost -0.10)

    Positioning:
        sys:protocol = HOW to operate (rules between core axioms and patterns)
        sys:trace    = WHAT is happening now (fine-grained agent execution logs)
    """

    op.execute("""
        INSERT INTO memory_decay_config (tag_pattern, decay_rate, half_life_days, auto_consolidate_threshold, priority_boost) VALUES
        ('sys:protocol', 0.002, 347, NULL,  0.30),
        ('sys:trace',    0.080, 9,   50,   -0.10)
        ON CONFLICT (tag_pattern) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM memory_decay_config WHERE tag_pattern IN ('sys:protocol', 'sys:trace');
    """)
