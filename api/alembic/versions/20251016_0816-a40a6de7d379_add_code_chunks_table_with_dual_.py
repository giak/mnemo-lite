"""add_code_chunks_table_with_dual_embeddings

Revision ID: a40a6de7d379
Revises: 9dde1f9db172
Create Date: 2025-10-16 08:16:47.361603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'a40a6de7d379'
down_revision: Union[str, Sequence[str], None] = '9dde1f9db172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create code_chunks table with dual embeddings (TEXT + CODE).

    Includes:
    - Dual VECTOR(768) embeddings (embedding_text, embedding_code)
    - HNSW indexes for both embeddings
    - GIN index for metadata (JSONB)
    - B-tree indexes for filtering (language, chunk_type, file_path)
    - Trigram indexes for similarity search (source_code, name)
    """

    # Create code_chunks table
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('language', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=True),
        sa.Column('end_line', sa.Integer(), nullable=True),
        sa.Column('embedding_text', pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column('embedding_code', pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_modified', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('node_id', sa.UUID(), nullable=True),
        sa.Column('repository', sa.Text(), nullable=True),
        sa.Column('commit_hash', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create HNSW index for embedding_text (semantic search on docstrings/comments)
    op.execute("""
        CREATE INDEX idx_code_embedding_text ON code_chunks
        USING hnsw (embedding_text vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # Create HNSW index for embedding_code (semantic search on code)
    op.execute("""
        CREATE INDEX idx_code_embedding_code ON code_chunks
        USING hnsw (embedding_code vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # Create GIN index for metadata (JSONB queries)
    op.execute("""
        CREATE INDEX idx_code_metadata ON code_chunks
        USING gin (metadata jsonb_path_ops);
    """)

    # Create B-tree indexes for filtering
    op.create_index('idx_code_language', 'code_chunks', ['language'])
    op.create_index('idx_code_type', 'code_chunks', ['chunk_type'])
    op.create_index('idx_code_file', 'code_chunks', ['file_path'])
    op.create_index('idx_code_indexed_at', 'code_chunks', ['indexed_at'])

    # Create trigram indexes for similarity search (pg_trgm)
    # First ensure pg_trgm extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.execute("""
        CREATE INDEX idx_code_source_trgm ON code_chunks
        USING gin (source_code gin_trgm_ops);
    """)

    op.execute("""
        CREATE INDEX idx_code_name_trgm ON code_chunks
        USING gin (name gin_trgm_ops);
    """)


def downgrade() -> None:
    """Drop code_chunks table and all indexes."""

    # Drop indexes first (explicit drops for manually created indexes)
    op.execute("DROP INDEX IF EXISTS idx_code_embedding_text;")
    op.execute("DROP INDEX IF EXISTS idx_code_embedding_code;")
    op.execute("DROP INDEX IF EXISTS idx_code_metadata;")
    op.execute("DROP INDEX IF EXISTS idx_code_source_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_code_name_trgm;")

    # Drop B-tree indexes (managed by Alembic)
    op.drop_index('idx_code_indexed_at', table_name='code_chunks')
    op.drop_index('idx_code_file', table_name='code_chunks')
    op.drop_index('idx_code_type', table_name='code_chunks')
    op.drop_index('idx_code_language', table_name='code_chunks')

    # Drop table
    op.drop_table('code_chunks')
