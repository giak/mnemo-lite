"""add outcome tracking columns to memories

Revision ID: 20260410_0000
Revises: 20260404_0000
Create Date: 2026-04-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = "20260410_0000"
down_revision = "20260404_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add outcome tracking columns with safe defaults
    op.execute("""
        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS outcome_positive INTEGER DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS outcome_negative INTEGER DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS outcome_score FLOAT
    """)
    op.execute("""
        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS last_outcome_at TIMESTAMPTZ
    """)

    # Create partial indexes for outcome columns
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_outcome_score
        ON memories(outcome_score)
        WHERE outcome_score IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_last_outcome
        ON memories(last_outcome_at)
        WHERE last_outcome_at IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_last_outcome")
    op.execute("DROP INDEX IF EXISTS idx_memories_outcome_score")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS last_outcome_at")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS outcome_score")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS outcome_negative")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS outcome_positive")
