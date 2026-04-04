"""add memory_relationships table

Revision ID: 20260404_0000
Revises: 20260403_0000
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260404_0000"
down_revision = "20260403_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_relationships",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.UUID, sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.UUID, sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("shared_entities", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("shared_concepts", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("shared_tags", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("relationship_types", postgresql.ARRAY(sa.Text), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("source_id != target_id", name="chk_no_self_loops"),
        sa.CheckConstraint("score >= 0.0 AND score <= 1.0", name="chk_score_range"),
        sa.UniqueConstraint("source_id", "target_id", name="uq_source_target"),
    )

    op.execute("CREATE INDEX idx_mem_rel_source ON memory_relationships(source_id)")
    op.execute("CREATE INDEX idx_mem_rel_target ON memory_relationships(target_id)")
    op.execute("CREATE INDEX idx_mem_rel_source_score ON memory_relationships(source_id, score DESC)")
    op.execute("CREATE INDEX idx_mem_rel_shared_entities ON memory_relationships USING GIN (shared_entities jsonb_path_ops)")
    op.execute("CREATE INDEX idx_mem_rel_shared_concepts ON memory_relationships USING GIN (shared_concepts jsonb_path_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_shared_concepts")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_shared_entities")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_source_score")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_target")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_source")
    op.drop_table("memory_relationships")
