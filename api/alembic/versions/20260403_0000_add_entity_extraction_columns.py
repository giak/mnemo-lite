"""add entity extraction columns to memories

Revision ID: 20260403_0000
Revises: 20260327_2315
Create Date: 2026-04-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260403_0000"
down_revision = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add entity extraction columns with safe defaults
    # Use postgresql.JSONB (not sa.JSON) for GIN index compatibility
    op.add_column(
        "memories",
        sa.Column(
            "entities", postgresql.JSONB,
            nullable=True, server_default="[]",
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "concepts", postgresql.JSONB,
            nullable=True, server_default="[]",
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "auto_tags", sa.Text,
            nullable=True, server_default="{}",
        ),
    )

    # GIN indexes for JSONB containment queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_entities_gin
        ON memories USING GIN (entities jsonb_path_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_concepts_gin
        ON memories USING GIN (concepts jsonb_path_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_concepts_gin")
    op.execute("DROP INDEX IF EXISTS idx_memories_entities_gin")
    op.drop_column("memories", "auto_tags")
    op.drop_column("memories", "concepts")
    op.drop_column("memories", "entities")
