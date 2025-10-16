"""baseline_existing_events_table

PHASE 0 - Story 0.1: Baseline NO-OP Migration

This migration establishes a baseline for Alembic to track the existing database schema.

Context:
- The 'events' table already exists (created via db/init/02-init.sql)
- This NO-OP migration tells Alembic: "start tracking from here"
- No actual schema changes are made (upgrade() = pass, downgrade() = pass)

Purpose:
- Avoid "relation already exists" errors
- Allow future migrations to build on this baseline
- Track schema evolution from this point forward

Next migrations (Phase 1+):
- Story 2bis: Create code_chunks table with dual embeddings
- Story 4: Create nodes + edges tables for dependency graph

Revision ID: 9dde1f9db172
Revises:
Create Date: 2025-10-15 20:29:30.809347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dde1f9db172'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
