"""add_consumption_tracking_to_memories

Revision ID: c4d7f2a8e102
Revises: b7c2e4f8a901
Create Date: 2026-03-27 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4d7f2a8e102'
down_revision: Union[str, Sequence[str], None] = 'b7c2e4f8a901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add consumption tracking to memories table.

    Enables agents (like Expanse Dream) to mark memories as "consumed"
    after processing them. Prevents re-processing and enables queries
    for fresh/unconsumed memories.

    Fields:
        consumed_at: When the memory was consumed (NULL = fresh)
        consumed_by: Who consumed it (e.g., "dream_passe1", "boot")

    Impact:
        - Dream can query only fresh drifts/traces
        - Boot can count fresh_drifts, fresh_traces
        - No breaking change (NULL = non consommé = comportement actuel)
    """

    op.execute("""
        ALTER TABLE memories
        ADD COLUMN consumed_at TIMESTAMPTZ DEFAULT NULL,
        ADD COLUMN consumed_by VARCHAR(100) DEFAULT NULL;
    """)

    # Partial index: only index non-consumed memories (the ones we query)
    op.execute("""
        CREATE INDEX idx_memories_fresh
        ON memories(consumed_at)
        WHERE consumed_at IS NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_fresh;")
    op.execute("""
        ALTER TABLE memories
        DROP COLUMN IF EXISTS consumed_at,
        DROP COLUMN IF EXISTS consumed_by;
    """)
