"""add_memories_content_trigram_index

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-02 11:00:00.000000

EPIC-32 Story 32.11: Add GIN trigram index on memories.content for
full-text lexical search. Previously lexical search skipped content
entirely (too slow without index). Now can search content efficiently.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GIN trigram index on memories.content and title."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
            ON memories USING GIN (content gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_title_trgm
            ON memories USING GIN (title gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_title_trgm")
    op.execute("DROP INDEX IF EXISTS idx_memories_content_trgm")
