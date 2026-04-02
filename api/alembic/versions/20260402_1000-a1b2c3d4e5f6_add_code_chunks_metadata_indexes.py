"""add_code_chunks_metadata_indexes

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d506
Create Date: 2026-04-02 10:00:00.000000

EPIC-32 Story 32.4: Add computed columns and indexes for JSONB filter optimization.
Previously metadata->>'repository' caused full table scans. Now uses
stored generated columns with B-tree indexes for O(log n) lookups.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d506'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add computed columns for frequently filtered JSONB paths.

    Before: metadata->>'repository' = :repo  (full scan, O(n))
    After:  repository = :repo               (index scan, O(log n))
    """
    op.execute("""
        ALTER TABLE code_chunks
        ADD COLUMN IF NOT EXISTS repository TEXT
            GENERATED ALWAYS AS (metadata->>'repository') STORED,
        ADD COLUMN IF NOT EXISTS return_type TEXT
            GENERATED ALWAYS AS (metadata->>'return_type') STORED
    """)

    # B-tree indexes for equality and prefix matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_chunks_repository
            ON code_chunks(repository)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_chunks_return_type
            ON code_chunks(return_type)
    """)

    # GIN index on full metadata for arbitrary JSONB queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_chunks_metadata_gin
            ON code_chunks USING GIN(metadata)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_code_chunks_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_code_chunks_return_type")
    op.execute("DROP INDEX IF EXISTS idx_code_chunks_repository")
    op.execute("""
        ALTER TABLE code_chunks
        DROP COLUMN IF EXISTS return_type,
        DROP COLUMN IF EXISTS repository
    """)
