"""Add transcript_chunks table with vector embeddings.

Revision ID: 003
Revises: 002
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create transcript_chunks table
    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(36),
            sa.ForeignKey("recordings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("speaker", sa.String(50), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create index on recording_id for efficient lookups
    op.create_index(
        "idx_transcript_chunks_recording_id",
        "transcript_chunks",
        ["recording_id"],
    )

    # Create HNSW index for approximate nearest neighbor search
    # This significantly speeds up similarity searches on large datasets
    op.execute(
        """
        CREATE INDEX idx_transcript_chunks_embedding_hnsw
        ON transcript_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_transcript_chunks_embedding_hnsw", table_name="transcript_chunks"
    )
    op.drop_index(
        "idx_transcript_chunks_recording_id", table_name="transcript_chunks"
    )
    op.drop_table("transcript_chunks")
